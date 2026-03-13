"""
InkPi 书法评测系统 - 合成数据集生成器

功能：
1. 从 models/templates/ 读取标准字帖
2. 使用数据增强生成三级质量数据：
   - good/: 轻微仿射变换（优秀书写）
   - medium/: 弹性形变 + 轻微腐蚀/膨胀（结构微塌）
   - poor/: 严重仿射变换 + 随机擦除（严重变形）
3. 保存到 data/synthetic/ 目录

依赖：仅使用 OpenCV + NumPy + SciPy（无需 albumentations）
"""
import cv2
import numpy as np
from pathlib import Path
from tqdm import tqdm
import argparse
import logging
import random
from scipy.ndimage import map_coordinates, gaussian_filter, zoom

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent
TEMPLATES_DIR = PROJECT_ROOT / "models" / "templates"
OUTPUT_DIR = PROJECT_ROOT / "data" / "synthetic"


class CalligraphyAugmentor:
    """书法数据增强器（纯 OpenCV + SciPy 实现）"""
    
    def __init__(self, seed: int = 42):
        np.random.seed(seed)
        random.seed(seed)
    
    def _apply_affine(
        self,
        image: np.ndarray,
        rotate_range: tuple,
        scale_range: tuple,
        translate_range: tuple,
        shear_range: tuple
    ) -> np.ndarray:
        """
        应用仿射变换
        
        Args:
            image: 输入图像
            rotate_range: (min, max) 旋转角度
            scale_range: (min, max) 缩放比例
            translate_range: (min, max) 平移像素
            shear_range: (min, max) 剪切角度
            
        Returns:
            变换后的图像
        """
        h, w = image.shape[:2]
        
        # 随机参数
        angle = np.random.uniform(rotate_range[0], rotate_range[1])
        scale = np.random.uniform(scale_range[0], scale_range[1])
        tx = np.random.uniform(translate_range[0], translate_range[1])
        ty = np.random.uniform(translate_range[0], translate_range[1])
        shear = np.random.uniform(shear_range[0], shear_range[1])
        
        # 中心点
        center = (w // 2, h // 2)
        
        # 旋转矩阵
        M_rot = cv2.getRotationMatrix2D(center, angle, scale)
        
        # 剪切
        shear_rad = np.deg2rad(shear)
        M_shear = np.array([
            [1, np.tan(shear_rad), 0],
            [0, 1, 0]
        ], dtype=np.float32)
        
        # 组合变换
        M = M_rot.copy()
        M[0, 2] += tx
        M[1, 2] += ty
        
        # 应用变换
        result = cv2.warpAffine(
            image, M, (w, h),
            flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=255
        )
        
        return result
    
    def _apply_elastic_transform(
        self,
        image: np.ndarray,
        alpha: float,
        sigma: float
    ) -> np.ndarray:
        """
        弹性形变（模拟手抖）
        
        Args:
            image: 输入图像
            alpha: 形变强度
            sigma: 平滑度
            
        Returns:
            变形后的图像
        """
        h, w = image.shape[:2]
        
        # 随机位移场
        dx = gaussian_filter(
            (np.random.rand(h, w) * 2 - 1) * alpha,
            sigma
        )
        dy = gaussian_filter(
            (np.random.rand(h, w) * 2 - 1) * alpha,
            sigma
        )
        
        # 创建坐标网格
        x, y = np.meshgrid(np.arange(w), np.arange(h))
        indices = (
            np.clip(y + dy, 0, h - 1).astype(np.float32),
            np.clip(x + dx, 0, w - 1).astype(np.float32)
        )
        
        # 应用变形
        if len(image.shape) == 3:
            result = np.zeros_like(image)
            for c in range(image.shape[2]):
                result[:, :, c] = map_coordinates(
                    image[:, :, c], indices, order=1, mode='constant', cval=255
                )
        else:
            result = map_coordinates(
                image, indices, order=1, mode='constant', cval=255
            )
        
        return result
    
    def _apply_grid_distortion(
        self,
        image: np.ndarray,
        num_steps: int,
        distort_limit: float
    ) -> np.ndarray:
        """
        网格畸变
        
        Args:
            image: 输入图像
            num_steps: 网格步数
            distort_limit: 畸变限制
            
        Returns:
            畸变后的图像
        """
        h, w = image.shape[:2]
        
        # 创建网格
        step_h = h // num_steps
        step_w = w // num_steps
        
        # 源点
        src_points = []
        dst_points = []
        
        for i in range(num_steps + 1):
            for j in range(num_steps + 1):
                src_x = j * step_w
                src_y = i * step_h
                
                # 随机偏移
                dx = np.random.uniform(-distort_limit, distort_limit) * step_w
                dy = np.random.uniform(-distort_limit, distort_limit) * step_h
                
                dst_x = np.clip(src_x + dx, 0, w - 1)
                dst_y = np.clip(src_y + dy, 0, h - 1)
                
                src_points.append([src_x, src_y])
                dst_points.append([dst_x, dst_y])
        
        src_points = np.array(src_points, dtype=np.float32)
        dst_points = np.array(dst_points, dtype=np.float32)
        
        # 计算变换矩阵
        M, _ = cv2.findHomography(src_points, dst_points)
        
        if M is None:
            return image
        
        result = cv2.warpPerspective(
            image, M, (w, h),
            flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=255
        )
        
        return result
    
    def _apply_coarse_dropout(
        self,
        image: np.ndarray,
        max_holes: int,
        max_size: int
    ) -> np.ndarray:
        """
        随机擦除（模拟断笔）
        
        Args:
            image: 输入图像
            max_holes: 最大擦除区域数
            max_size: 最大擦除区域尺寸
            
        Returns:
            擦除后的图像
        """
        result = image.copy()
        h, w = image.shape[:2]
        
        num_holes = np.random.randint(1, max_holes + 1)
        
        for _ in range(num_holes):
            hole_h = np.random.randint(5, max_size + 1)
            hole_w = np.random.randint(5, max_size + 1)
            
            y = np.random.randint(0, h - hole_h)
            x = np.random.randint(0, w - hole_w)
            
            if len(result.shape) == 3:
                result[y:y+hole_h, x:x+hole_w] = 255
            else:
                result[y:y+hole_h, x:x+hole_w] = 255
        
        return result
    
    def _apply_gaussian_noise(
        self,
        image: np.ndarray,
        var_limit: tuple
    ) -> np.ndarray:
        """
        添加高斯噪声
        
        Args:
            image: 输入图像
            var_limit: 方差范围
            
        Returns:
            添加噪声后的图像
        """
        var = np.random.uniform(var_limit[0], var_limit[1])
        sigma = np.sqrt(var)
        
        noise = np.random.normal(0, sigma, image.shape).astype(np.float32)
        noisy = image.astype(np.float32) + noise
        
        return np.clip(noisy, 0, 255).astype(np.uint8)
    
    def _apply_gaussian_blur(
        self,
        image: np.ndarray,
        ksize_range: tuple
    ) -> np.ndarray:
        """
        高斯模糊
        
        Args:
            image: 输入图像
            ksize_range: 核大小范围 (min, max)，必须为奇数
            
        Returns:
            模糊后的图像
        """
        ksize = np.random.randint(ksize_range[0] // 2, ksize_range[1] // 2 + 1) * 2 + 1
        ksize = max(3, ksize)
        
        return cv2.GaussianBlur(image, (ksize, ksize), 0)
    
    def _apply_brightness_contrast(
        self,
        image: np.ndarray,
        brightness_limit: tuple,
        contrast_limit: tuple
    ) -> np.ndarray:
        """
        亮度对比度调整
        
        Args:
            image: 输入图像
            brightness_limit: 亮度调整范围 (-1, 1)
            contrast_limit: 对比度调整范围 (-1, 1)
            
        Returns:
            调整后的图像
        """
        brightness = np.random.uniform(brightness_limit[0], brightness_limit[1])
        contrast = np.random.uniform(contrast_limit[0], contrast_limit[1])
        
        # 亮度
        if brightness > 0:
            image = cv2.add(image, np.array([int(brightness * 255)]))
        else:
            image = cv2.subtract(image, np.array([int(-brightness * 255)]))
        
        # 对比度
        contrast_factor = 1.0 + contrast
        mean = np.mean(image)
        image = cv2.addWeighted(
            image, contrast_factor,
            np.full_like(image, mean), 1 - contrast_factor, 0
        )
        
        return np.clip(image, 0, 255).astype(np.uint8)
    
    def _apply_perspective(
        self,
        image: np.ndarray,
        scale: float
    ) -> np.ndarray:
        """
        透视变换
        
        Args:
            image: 输入图像
            scale: 变换强度
            
        Returns:
            变换后的图像
        """
        h, w = image.shape[:2]
        
        # 源点（四个角）
        src_points = np.array([
            [0, 0],
            [w - 1, 0],
            [w - 1, h - 1],
            [0, h - 1]
        ], dtype=np.float32)
        
        # 目标点（添加随机偏移）
        dst_points = src_points.copy()
        for i in range(4):
            dst_points[i, 0] += np.random.uniform(-w * scale, w * scale)
            dst_points[i, 1] += np.random.uniform(-h * scale, h * scale)
        
        # 计算透视变换矩阵
        M = cv2.getPerspectiveTransform(src_points, dst_points)
        
        result = cv2.warpPerspective(
            image, M, (w, h),
            flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=255
        )
        
        return result
    
    def apply_morphology(self, image: np.ndarray, quality: str) -> np.ndarray:
        """
        应用形态学操作（腐蚀/膨胀）
        
        Args:
            image: 输入图像
            quality: 质量级别
            
        Returns:
            处理后的图像
        """
        if quality == "medium":
            if np.random.random() < 0.5:
                kernel = np.ones((2, 2), np.uint8)
                image = cv2.erode(image, kernel, iterations=1)
            else:
                kernel = np.ones((2, 2), np.uint8)
                image = cv2.dilate(image, kernel, iterations=1)
        elif quality == "poor":
            if np.random.random() < 0.5:
                kernel = np.ones((3, 3), np.uint8)
                image = cv2.erode(image, kernel, iterations=np.random.randint(1, 3))
            else:
                kernel = np.ones((3, 3), np.uint8)
                image = cv2.dilate(image, kernel, iterations=np.random.randint(1, 3))
        
        return image
    
    def transform(self, image: np.ndarray, quality: str) -> np.ndarray:
        """
        根据质量级别进行变换
        
        Args:
            image: 输入图像 (H, W) 灰度图
            quality: 'good', 'medium', 'poor'
            
        Returns:
            变换后的图像
        """
        result = image.copy()
        
        if quality == "good":
            # 轻微仿射变换
            if np.random.random() < 0.8:
                result = self._apply_affine(
                    result,
                    rotate_range=(-5, 5),
                    scale_range=(0.97, 1.03),
                    translate_range=(-2, 2),
                    shear_range=(-2, 2)
                )
            
            # 轻微噪声
            if np.random.random() < 0.3:
                result = self._apply_gaussian_noise(result, (10, 30))
            
            # 轻微模糊
            if np.random.random() < 0.2:
                result = self._apply_gaussian_blur(result, (3, 5))
        
        elif quality == "medium":
            # 仿射变换
            if np.random.random() < 0.9:
                result = self._apply_affine(
                    result,
                    rotate_range=(-10, 10),
                    scale_range=(0.92, 1.08),
                    translate_range=(-5, 5),
                    shear_range=(-5, 5)
                )
            
            # 弹性形变
            if np.random.random() < 0.7:
                result = self._apply_elastic_transform(result, alpha=20, sigma=5)
            
            # 网格畸变
            if np.random.random() < 0.5:
                result = self._apply_grid_distortion(result, num_steps=5, distort_limit=0.1)
            
            # 噪声
            if np.random.random() < 0.4:
                result = self._apply_gaussian_noise(result, (20, 50))
            
            # 模糊
            if np.random.random() < 0.3:
                result = self._apply_gaussian_blur(result, (3, 7))
            
            # 亮度对比度
            if np.random.random() < 0.5:
                result = self._apply_brightness_contrast(
                    result,
                    brightness_limit=(-0.1, 0.1),
                    contrast_limit=(-0.1, 0.1)
                )
            
            # 形态学
            result = self.apply_morphology(result, quality)
        
        elif quality == "poor":
            # 严重仿射变换
            result = self._apply_affine(
                result,
                rotate_range=(-30, 30),
                scale_range=(0.75, 1.25),
                translate_range=(-15, 15),
                shear_range=(-15, 15)
            )
            
            # 严重弹性形变
            if np.random.random() < 0.8:
                result = self._apply_elastic_transform(result, alpha=40, sigma=10)
            
            # 网格畸变
            if np.random.random() < 0.7:
                result = self._apply_grid_distortion(result, num_steps=5, distort_limit=0.2)
            
            # 随机擦除
            if np.random.random() < 0.6:
                result = self._apply_coarse_dropout(result, max_holes=8, max_size=30)
            
            # 强噪声
            if np.random.random() < 0.6:
                result = self._apply_gaussian_noise(result, (30, 80))
            
            # 严重模糊
            if np.random.random() < 0.5:
                result = self._apply_gaussian_blur(result, (5, 11))
            
            # 亮度对比度
            if np.random.random() < 0.7:
                result = self._apply_brightness_contrast(
                    result,
                    brightness_limit=(-0.2, 0.2),
                    contrast_limit=(-0.3, 0.1)
                )
            
            # 透视变换
            if np.random.random() < 0.5:
                result = self._apply_perspective(result, scale=0.1)
            
            # 形态学
            result = self.apply_morphology(result, quality)
        
        else:
            raise ValueError(f"Unknown quality: {quality}")
        
        return result


def load_templates(templates_dir: Path) -> dict:
    """
    加载所有字帖
    
    Args:
        templates_dir: 字帖目录
        
    Returns:
        {字符: 图像} 字典
    """
    templates = {}
    
    if not templates_dir.exists():
        logger.warning(f"字帖目录不存在: {templates_dir}")
        return templates
    
    for file_path in templates_dir.glob("*.png"):
        char = file_path.stem.split("_")[0]  # 提取字符
        image = cv2.imread(str(file_path), cv2.IMREAD_GRAYSCALE)
        if image is not None:
            templates[char] = image
            logger.info(f"加载字帖: {char} ({file_path.name})")
    
    logger.info(f"共加载 {len(templates)} 个字帖")
    return templates


def generate_sample_image(char: str = "永", size: int = 224) -> np.ndarray:
    """
    生成示例字帖图像（用于测试）
    
    Args:
        char: 字符
        size: 图像尺寸
        
    Returns:
        生成的图像
    """
    # 创建白色背景
    image = np.ones((size, size), dtype=np.uint8) * 255
    
    # 绘制字符（使用 OpenCV 默认字体）
    font = cv2.FONT_HERSHEY_SIMPLEX
    text_size = cv2.getTextSize(char, font, 5, 3)[0]
    text_x = (size - text_size[0]) // 2
    text_y = (size + text_size[1]) // 2
    
    cv2.putText(image, char, (text_x, text_y), font, 5, 0, 3)
    
    return image


def build_dataset(
    templates_dir: Path = None,
    output_dir: Path = None,
    samples_per_quality: int = 100,
    quality_levels: list = None,
    seed: int = 42
):
    """
    构建合成数据集
    
    Args:
        templates_dir: 字帖目录
        output_dir: 输出目录
        samples_per_quality: 每个质量级别的样本数
        quality_levels: 要生成的质量级别
        seed: 随机种子
    """
    if templates_dir is None:
        templates_dir = TEMPLATES_DIR
    if output_dir is None:
        output_dir = OUTPUT_DIR
    if quality_levels is None:
        quality_levels = ["good", "medium", "poor"]
    
    np.random.seed(seed)
    random.seed(seed)
    
    logger.info("=" * 60)
    logger.info("🚀 开始构建合成数据集")
    logger.info("=" * 60)
    logger.info(f"字帖目录: {templates_dir}")
    logger.info(f"输出目录: {output_dir}")
    logger.info(f"每级样本数: {samples_per_quality}")
    logger.info(f"质量级别: {quality_levels}")
    
    # 加载字帖
    templates = load_templates(templates_dir)
    
    # 如果没有字帖，生成示例
    if not templates:
        logger.warning("未找到字帖，生成示例数据...")
        templates_dir.mkdir(parents=True, exist_ok=True)
        
        sample_chars = ["永", "山", "水", "火", "土", "木", "金", "人", "大", "小"]
        for char in sample_chars:
            image = generate_sample_image(char)
            templates[char] = image
            
            # 保存到字帖目录
            cv2.imwrite(str(templates_dir / f"{char}_楷书_标准.png"), image)
            logger.info(f"生成示例字帖: {char}")
    
    # 创建输出目录
    for quality in quality_levels:
        (output_dir / quality).mkdir(parents=True, exist_ok=True)
    
    # 数据增强器
    augmentor = CalligraphyAugmentor(seed=seed)
    
    # 统计
    total_generated = 0
    
    # 为每个字帖生成增强样本
    for char, template in templates.items():
        logger.info(f"\n📝 处理字符: {char}")
        
        for quality in quality_levels:
            quality_dir = output_dir / quality
            
            for i in tqdm(range(samples_per_quality), desc=f"  {quality}"):
                # 应用变换
                augmented = augmentor.transform(template, quality)
                
                # 保存
                filename = f"{char}_{quality}_{i:04d}.png"
                filepath = quality_dir / filename
                cv2.imwrite(str(filepath), augmented)
                
                total_generated += 1
    
    # 复制原始字帖到 originals 目录（作为完美参考）
    originals_dir = output_dir / "originals"
    originals_dir.mkdir(parents=True, exist_ok=True)
    for char, template in templates.items():
        cv2.imwrite(str(originals_dir / f"{char}.png"), template)
    
    logger.info("\n" + "=" * 60)
    logger.info(f"✅ 数据集构建完成!")
    logger.info(f"   总样本数: {total_generated}")
    logger.info(f"   原始字帖: {len(templates)}")
    logger.info(f"   输出目录: {output_dir}")
    logger.info("=" * 60)
    
    # 打印目录结构
    logger.info("\n📁 目录结构:")
    for quality in quality_levels + ["originals"]:
        count = len(list((output_dir / quality).glob("*.png")))
        logger.info(f"   {quality}/: {count} 张图像")


def main():
    parser = argparse.ArgumentParser(description="InkPi 合成数据集生成器")
    parser.add_argument(
        "--templates", "-t",
        type=str,
        default=str(TEMPLATES_DIR),
        help="字帖目录路径"
    )
    parser.add_argument(
        "--output", "-o",
        type=str,
        default=str(OUTPUT_DIR),
        help="输出目录路径"
    )
    parser.add_argument(
        "--samples", "-n",
        type=int,
        default=100,
        help="每个质量级别的样本数"
    )
    parser.add_argument(
        "--quality", "-q",
        type=str,
        nargs="+",
        default=["good", "medium", "poor"],
        help="要生成的质量级别"
    )
    parser.add_argument(
        "--seed", "-s",
        type=int,
        default=42,
        help="随机种子"
    )
    
    args = parser.parse_args()
    
    build_dataset(
        templates_dir=Path(args.templates),
        output_dir=Path(args.output),
        samples_per_quality=args.samples,
        quality_levels=args.quality,
        seed=args.seed
    )


if __name__ == "__main__":
    main()