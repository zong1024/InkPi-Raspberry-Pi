#!/usr/bin/env python3
"""
InkPi 书法评测系统 - 真实数据集下载脚本

支持的公开数据集:
1. Chinese Calligraphy Styles (GitHub) - 多风格真实书法
2. HWDB (CASIA) - 手写汉字数据库
3. 自定义采集 - 支持本地数据导入

使用方法:
    python training/download_real_dataset.py --source github
    python training/download_real_dataset.py --source kaggle
    python training/download_real_dataset.py --source local --input /path/to/images
"""
import os
import sys
import argparse
import subprocess
import zipfile
import tarfile
import shutil
from pathlib import Path
from typing import List, Dict, Optional
import logging
import json
import random

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
REAL_DATA_DIR = DATA_DIR / "real"

# 书法风格分类
STYLE_NAMES = {
    "kaishu": "楷书",
    "xingshu": "行书", 
    "caoshu": "草书",
    "lishu": "隶书",
    "zhuanshu": "篆书"
}

# 数据集配置
DATASETS = {
    "github": {
        "name": "Chinese Calligraphy Styles (GitHub)",
        "url": "https://github.com/MingtaoGuo/CNN-for-Chinese-Calligraphy-Styles-classification/archive/refs/heads/master.zip",
        "description": "包含楷书、行书、草书、隶书、篆书五种风格的真实书法图片",
        "size": "~200MB",
        "license": "MIT"
    },
    "kaggle_styles": {
        "name": "Chinese Calligraphy Styles (Kaggle)",
        "url": "kaggle datasets download -d dongwujin/chinese-calligraphy-styles",
        "description": "50,000+ 张多风格书法图片",
        "size": "~1GB",
        "license": "CC0"
    },
    "kaggle_characters": {
        "name": "Chinese Calligraphy Characters (Kaggle)",
        "url": "kaggle datasets download -d kelizhao/chinese-calligraphy-characters",
        "description": "按字符分类的书法图片",
        "size": "~500MB",
        "license": "Research"
    },
    "hwdb": {
        "name": "CASIA HWDB",
        "url": "http://www.nlpr.ia.ac.cn/databases/handwriting/Download.html",
        "description": "中科院手写汉字数据库，需要手动下载",
        "size": "~3GB",
        "license": "Research"
    }
}


class RealDatasetDownloader:
    """真实书法数据集下载器"""
    
    def __init__(self):
        self.data_dir = REAL_DATA_DIR
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
    def download_github_dataset(self) -> bool:
        """下载 GitHub 上的书法数据集"""
        logger.info("开始下载 GitHub 书法数据集...")
        
        url = DATASETS["github"]["url"]
        zip_path = self.data_dir / "github_dataset.zip"
        extract_dir = self.data_dir / "github_temp"
        
        try:
            # 下载
            logger.info(f"下载中: {url}")
            result = subprocess.run(
                ["curl", "-L", "-o", str(zip_path), url],
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                logger.error(f"下载失败: {result.stderr}")
                return False
            
            # 解压
            logger.info("解压中...")
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(extract_dir)
            
            # 整理目录结构
            self._organize_github_data(extract_dir)
            
            # 清理
            zip_path.unlink()
            shutil.rmtree(extract_dir)
            
            logger.info("✅ GitHub 数据集下载完成!")
            return True
            
        except Exception as e:
            logger.error(f"下载失败: {e}")
            return False
    
    def download_kaggle_dataset(self, dataset_key: str = "kaggle_styles") -> bool:
        """下载 Kaggle 数据集 (需要 Kaggle API)"""
        logger.info(f"开始下载 Kaggle 数据集: {dataset_key}")
        
        # 检查 Kaggle API
        try:
            result = subprocess.run(["kaggle", "--version"], capture_output=True)
            if result.returncode != 0:
                logger.error("❌ 未安装 Kaggle CLI，请先安装: pip install kaggle")
                logger.info("并配置 API Token: https://www.kaggle.com/docs/api")
                return False
        except FileNotFoundError:
            logger.error("❌ 未安装 Kaggle CLI")
            return False
        
        dataset_url = DATASETS[dataset_key]["url"]
        output_dir = self.data_dir / f"kaggle_{dataset_key}"
        
        try:
            # 下载
            logger.info(f"执行: {dataset_url}")
            result = subprocess.run(
                dataset_url.split(),
                cwd=str(self.data_dir),
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                logger.error(f"下载失败: {result.stderr}")
                return False
            
            # 解压
            zip_files = list(self.data_dir.glob("*.zip"))
            for zf in zip_files:
                logger.info(f"解压: {zf}")
                with zipfile.ZipFile(zf, 'r') as zip_ref:
                    zip_ref.extractall(output_dir)
                zf.unlink()
            
            # 整理
            self._organize_kaggle_data(output_dir, dataset_key)
            
            logger.info(f"✅ Kaggle {dataset_key} 数据集下载完成!")
            return True
            
        except Exception as e:
            logger.error(f"下载失败: {e}")
            return False
    
    def import_local_dataset(self, input_path: str, style: str = None, quality: str = "good") -> bool:
        """
        导入本地数据集
        
        Args:
            input_path: 本地图片目录路径
            style: 书法风格 (kaishu, xingshu, caoshu, lishu, zhuanshu)
            quality: 质量标签 (good, medium, poor)
        """
        logger.info(f"导入本地数据集: {input_path}")
        
        input_dir = Path(input_path)
        if not input_dir.exists():
            logger.error(f"目录不存在: {input_path}")
            return False
        
        # 支持的图片格式
        image_extensions = {'.png', '.jpg', '.jpeg', '.bmp', '.gif'}
        
        # 查找所有图片
        images = []
        for ext in image_extensions:
            images.extend(input_dir.rglob(f"*{ext}"))
            images.extend(input_dir.rglob(f"*{ext.upper()}"))
        
        if not images:
            logger.error("未找到图片文件")
            return False
        
        logger.info(f"找到 {len(images)} 张图片")
        
        # 确定目标目录
        if style:
            target_dir = self.data_dir / style / quality
        else:
            target_dir = self.data_dir / "mixed" / quality
        
        target_dir.mkdir(parents=True, exist_ok=True)
        
        # 复制图片
        for i, img_path in enumerate(images):
            target_file = target_dir / f"img_{i:06d}{img_path.suffix}"
            shutil.copy2(img_path, target_file)
            
            if (i + 1) % 100 == 0:
                logger.info(f"已复制 {i + 1}/{len(images)} 张图片...")
        
        logger.info(f"✅ 导入完成: {len(images)} 张图片 -> {target_dir}")
        return True
    
    def _organize_github_data(self, extract_dir: Path):
        """整理 GitHub 数据集目录结构 (兼容训练脚本)"""
        logger.info("整理目录结构...")
        
        # 查找解压后的目录
        extracted_dirs = list(extract_dir.glob("CNN-for-Chinese-Calligraphy-Styles-classification*"))
        if not extracted_dirs:
            logger.warning("未找到解压目录")
            return
        
        source_dir = extracted_dirs[0]
        
        # 创建训练脚本需要的目录结构
        originals_dir = self.data_dir / "originals"
        good_dir = self.data_dir / "good"
        medium_dir = self.data_dir / "medium"
        poor_dir = self.data_dir / "poor"
        
        for d in [originals_dir, good_dir, medium_dir, poor_dir]:
            d.mkdir(parents=True, exist_ok=True)
        
        # 遍历并整理
        all_images = []
        for style_dir in source_dir.iterdir():
            if style_dir.is_dir() and style_dir.name.lower() in STYLE_NAMES:
                style_name = style_dir.name.lower()
                
                # 复制图片
                images = list(style_dir.glob("*.png")) + list(style_dir.glob("*.jpg"))
                for img in images:
                    # 使用风格名作为前缀
                    target_file = self.data_dir / f"{style_name}_{img.name}"
                    if not target_file.exists():
                        shutil.copy2(img, target_file)
                    all_images.append((target_file, style_name))
                
                logger.info(f"  {STYLE_NAMES[style_name]}: {len(images)} 张图片")
        
        # 按风格质量分配到 good/medium/poor
        # 楷书 -> good, 行书/隶书 -> medium, 草书/篆书 -> poor
        style_to_quality = {
            "kaishu": "good",
            "xingshu": "medium",
            "lishu": "medium",
            "caoshu": "poor",
            "zhuanshu": "poor"
        }
        
        # 按质量分类复制
        for img_path, style in all_images:
            quality = style_to_quality.get(style, "medium")
            target_dir = self.data_dir / quality
            target_file = target_dir / img_path.name
            if not target_file.exists():
                shutil.move(str(img_path), str(target_file))
        
        # 复制标准字帖作为 originals (使用楷书第一张)
        kaishu_dir = self.data_dir / "good"
        kaishu_images = list(kaishu_dir.glob("kaishu_*.png"))
        if kaishu_images:
            # 复制几张作为标准字帖
            chars_seen = set()
            for img in kaishu_images[:20]:
                # 提取字符名
                char_name = img.stem.replace("kaishu_", "").rsplit("_", 1)[0]
                if char_name not in chars_seen:
                    shutil.copy2(img, originals_dir / f"{char_name}.png")
                    chars_seen.add(char_name)
        
        # 清理临时文件
        for img in self.data_dir.glob("*.png"):
            if img.parent == self.data_dir:
                img.unlink()
    
    def _organize_kaggle_data(self, output_dir: Path, dataset_key: str):
        """整理 Kaggle 数据集目录结构"""
        logger.info("整理 Kaggle 数据...")
        
        # 根据不同数据集结构调整
        if "styles" in dataset_key:
            # Chinese Calligraphy Styles 数据集
            for style_dir in output_dir.iterdir():
                if style_dir.is_dir():
                    style_name = style_dir.name.lower()
                    if style_name in STYLE_NAMES:
                        target_dir = self.data_dir / style_name
                        target_dir.mkdir(parents=True, exist_ok=True)
                        
                        images = list(style_dir.glob("**/*.png")) + list(style_dir.glob("**/*.jpg"))
                        for img in images:
                            target_file = target_dir / img.name
                            if not target_file.exists():
                                shutil.copy2(img, target_file)
    
    def generate_labels_csv(self):
        """生成标签文件 (用于训练)"""
        logger.info("生成标签文件...")
        
        labels = []
        
        for style_name in STYLE_NAMES.keys():
            style_dir = self.data_dir / style_name
            if style_dir.exists():
                for img_path in style_dir.glob("*.png"):
                    labels.append({
                        "path": str(img_path.relative_to(self.data_dir)),
                        "style": style_name,
                        "style_cn": STYLE_NAMES[style_name],
                        "quality": "unknown"
                    })
        
        # 混合风格
        mixed_dir = self.data_dir / "mixed"
        if mixed_dir.exists():
            for quality in ["good", "medium", "poor"]:
                quality_dir = mixed_dir / quality
                if quality_dir.exists():
                    for img_path in quality_dir.glob("*.png"):
                        labels.append({
                            "path": str(img_path.relative_to(self.data_dir)),
                            "style": "mixed",
                            "style_cn": "混合",
                            "quality": quality
                        })
        
        # 保存 CSV
        import csv
        csv_path = self.data_dir / "labels.csv"
        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=["path", "style", "style_cn", "quality"])
            writer.writeheader()
            writer.writerows(labels)
        
        logger.info(f"✅ 生成标签文件: {csv_path} ({len(labels)} 条记录)")
        
        # 统计
        self._print_statistics()
    
    def _print_statistics(self):
        """打印数据集统计信息"""
        print("\n" + "="*50)
        print("📊 数据集统计")
        print("="*50)
        
        total = 0
        for style_name, style_cn in STYLE_NAMES.items():
            style_dir = self.data_dir / style_name
            count = len(list(style_dir.glob("*.png"))) + len(list(style_dir.glob("*.jpg")))
            if count > 0:
                print(f"  {style_cn} ({style_name}): {count} 张")
                total += count
        
        mixed_dir = self.data_dir / "mixed"
        if mixed_dir.exists():
            for quality in ["good", "medium", "poor"]:
                quality_dir = mixed_dir / quality
                count = len(list(quality_dir.glob("*.png"))) + len(list(quality_dir.glob("*.jpg")))
                if count > 0:
                    print(f"  混合/{quality}: {count} 张")
                    total += count
        
        print(f"\n  📁 总计: {total} 张图片")
        print(f"  📂 目录: {self.data_dir}")
        print("="*50 + "\n")


def main():
    parser = argparse.ArgumentParser(description="InkPi 真实书法数据集下载器")
    parser.add_argument("--source", type=str, choices=["github", "kaggle", "kaggle_styles", "kaggle_characters", "local", "stats"],
                       default="github", help="数据源")
    parser.add_argument("--input", type=str, help="本地数据目录 (source=local 时使用)")
    parser.add_argument("--style", type=str, choices=list(STYLE_NAMES.keys()),
                       help="书法风格 (source=local 时使用)")
    parser.add_argument("--quality", type=str, choices=["good", "medium", "poor"],
                       default="good", help="质量标签 (source=local 时使用)")
    parser.add_argument("--labels", action="store_true", help="仅生成标签文件")
    
    args = parser.parse_args()
    
    downloader = RealDatasetDownloader()
    
    if args.labels or args.source == "stats":
        downloader.generate_labels_csv()
        return
    
    if args.source == "github":
        success = downloader.download_github_dataset()
    elif args.source.startswith("kaggle"):
        success = downloader.download_kaggle_dataset(args.source)
    elif args.source == "local":
        if not args.input:
            print("❌ 请指定 --input 参数")
            sys.exit(1)
        success = downloader.import_local_dataset(args.input, args.style, args.quality)
    else:
        print(f"❌ 未知数据源: {args.source}")
        sys.exit(1)
    
    if success:
        downloader.generate_labels_csv()
        print("\n✅ 数据集准备完成!")
        print("\n下一步: 更新训练脚本使用真实数据")
        print("  python training/train_siamese.py --data data/real")
    else:
        print("\n❌ 数据集下载失败")
        sys.exit(1)


if __name__ == "__main__":
    main()