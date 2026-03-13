"""
InkPi 书法评测系统 - 孪生网络训练脚本

功能：
1. MobileNetV3-Small 骨干的孪生网络
2. CosineEmbeddingLoss 损失函数
3. 标准训练循环 + 验证监控
4. 导出 ONNX 模型

模型架构：
- 输入：单通道 224x224 图像
- 骨干：MobileNetV3-Small (修改第一层)
- 输出：128 维特征向量
"""
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader
from torchvision.models import mobilenet_v3_small
from torchvision import transforms
from pathlib import Path
from tqdm import tqdm
import numpy as np
import cv2
import logging
import argparse
from datetime import datetime
import random

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data" / "synthetic"
OUTPUT_DIR = PROJECT_ROOT / "models"


# ============ 模型定义 ============

class SiameseNet(nn.Module):
    """
    孪生网络
    
    架构：
    - 骨干：MobileNetV3-Small
    - 输入：[B, 1, 224, 224] 灰度图
    - 输出：[B, 128] 特征向量
    """
    
    def __init__(self, pretrained: bool = False):
        super().__init__()
        
        # 加载 MobileNetV3-Small
        self.backbone = mobilenet_v3_small(pretrained=pretrained)
        
        # 修改第一层卷积：3通道 → 1通道
        # 原始：Conv2d(3, 16, kernel_size=3, stride=2, padding=1)
        original_conv = self.backbone.features[0][0]
        self.backbone.features[0][0] = nn.Conv2d(
            in_channels=1,              # 单通道输入
            out_channels=original_conv.out_channels,
            kernel_size=original_conv.kernel_size,
            stride=original_conv.stride,
            padding=original_conv.padding,
            bias=False
        )
        
        # 用原始权重的均值初始化新卷积层（如果使用预训练）
        if pretrained:
            with torch.no_grad():
                # 将 RGB 权重平均到单通道
                self.backbone.features[0][0].weight.data = (
                    original_conv.weight.data.mean(dim=1, keepdim=True)
                )
        
        # 修改分类头：1000类 → 128维特征
        # 原始：Linear(576, 1024) → Hardswish → Dropout → Linear(1024, 1000)
        self.backbone.classifier = nn.Sequential(
            nn.Linear(576, 256),
            nn.Hardswish(inplace=True),
            nn.Dropout(p=0.2, inplace=True),
            nn.Linear(256, 128)  # 输出 128 维特征
        )
    
    def forward_one(self, x: torch.Tensor) -> torch.Tensor:
        """
        单分支前向传播
        
        Args:
            x: [B, 1, 224, 224]
            
        Returns:
            [B, 128] L2 归一化特征向量
        """
        features = self.backbone(x)
        # L2 归一化
        features = F.normalize(features, p=2, dim=1)
        return features
    
    def forward(self, x1: torch.Tensor, x2: torch.Tensor) -> tuple:
        """
        孪生前向传播
        
        Args:
            x1: [B, 1, 224, 224] 输入1（字帖）
            x2: [B, 1, 224, 224] 输入2（用户书写）
            
        Returns:
            Tuple[[B, 128], [B, 128]] 两个特征向量
        """
        feat1 = self.forward_one(x1)
        feat2 = self.forward_one(x2)
        return feat1, feat2
    
    def get_similarity(self, x1: torch.Tensor, x2: torch.Tensor) -> torch.Tensor:
        """
        计算余弦相似度
        
        Args:
            x1, x2: 输入图像
            
        Returns:
            [B] 余弦相似度（-1 到 1）
        """
        feat1, feat2 = self.forward(x1, x2)
        # 由于已经 L2 归一化，点积即为余弦相似度
        similarity = (feat1 * feat2).sum(dim=1)
        return similarity


# ============ 数据集定义 ============

class SiameseDataset(Dataset):
    """
    孪生网络数据集
    
    结构：
    - originals/: 原始字帖
    - good/: 优秀样本（目标值 1.0）
    - medium/: 中等样本（目标值 0.3）
    - poor/: 差样本（目标值 -1.0）
    """
    
    # 目标值映射
    QUALITY_TARGETS = {
        "good": 1.0,
        "medium": 0.3,
        "poor": -1.0
    }
    
    def __init__(
        self,
        data_dir: Path,
        quality_levels: list = None,
        transform=None,
        split: str = "train",
        train_ratio: float = 0.8,
        seed: int = 42
    ):
        if quality_levels is None:
            quality_levels = ["good", "medium", "poor"]
        
        self.data_dir = Path(data_dir)
        self.quality_levels = quality_levels
        self.transform = transform
        self.split = split
        
        # 加载原始字帖
        self.templates = {}
        originals_dir = self.data_dir / "originals"
        if originals_dir.exists():
            for img_path in originals_dir.glob("*.png"):
                char = img_path.stem
                self.templates[char] = img_path
        
        # 构建样本列表
        self.samples = []
        for quality in quality_levels:
            quality_dir = self.data_dir / quality
            if not quality_dir.exists():
                continue
            
            target = self.QUALITY_TARGETS[quality]
            
            for img_path in quality_dir.glob("*.png"):
                # 提取字符名
                char = img_path.stem.split("_")[0]
                
                if char in self.templates:
                    self.samples.append({
                        "template_path": self.templates[char],
                        "sample_path": img_path,
                        "quality": quality,
                        "target": target,
                        "char": char
                    })
        
        # 打乱并划分训练/验证集
        random.seed(seed)
        random.shuffle(self.samples)
        
        split_idx = int(len(self.samples) * train_ratio)
        if split == "train":
            self.samples = self.samples[:split_idx]
        elif split == "val":
            self.samples = self.samples[split_idx:]
        
        logger.info(f"[{split}] 加载 {len(self.samples)} 个样本对")
    
    def __len__(self):
        return len(self.samples)
    
    def __getitem__(self, idx):
        sample = self.samples[idx]
        
        # 加载图像
        template = cv2.imread(str(sample["template_path"]), cv2.IMREAD_GRAYSCALE)
        user_sample = cv2.imread(str(sample["sample_path"]), cv2.IMREAD_GRAYSCALE)
        
        # 归一化到 [0, 1]
        template = template.astype(np.float32) / 255.0
        user_sample = user_sample.astype(np.float32) / 255.0
        
        # 应用变换
        if self.transform:
            template = self.transform(template)
            user_sample = self.transform(user_sample)
        else:
            # 默认转换为 Tensor
            template = torch.from_numpy(template).unsqueeze(0)
            user_sample = torch.from_numpy(user_sample).unsqueeze(0)
        
        return {
            "template": template,
            "sample": user_sample,
            "target": torch.tensor(sample["target"], dtype=torch.float32),
            "quality": sample["quality"],
            "char": sample["char"]
        }


# ============ 训练函数 ============

def train_one_epoch(
    model: nn.Module,
    dataloader: DataLoader,
    criterion: nn.Module,
    optimizer: torch.optim.Optimizer,
    device: torch.device,
    epoch: int
) -> dict:
    """
    训练一个 Epoch
    """
    model.train()
    total_loss = 0.0
    correct = 0
    total = 0
    
    pbar = tqdm(dataloader, desc=f"Epoch {epoch} [Train]")
    
    for batch in pbar:
        # 获取数据
        template = batch["template"].to(device)
        sample = batch["sample"].to(device)
        target = batch["target"].to(device)
        
        # 前向传播
        feat1, feat2 = model(template, sample)
        
        # 计算损失
        loss = criterion(feat1, feat2, target)
        
        # 反向传播
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()
        
        # 统计
        total_loss += loss.item() * template.size(0)
        
        # 计算准确率（相似度与目标同号）
        with torch.no_grad():
            similarity = (feat1 * feat2).sum(dim=1)
            pred_positive = similarity > 0
            target_positive = target > 0
            correct += (pred_positive == target_positive).sum().item()
            total += template.size(0)
        
        # 更新进度条
        pbar.set_postfix({
            "loss": f"{loss.item():.4f}",
            "acc": f"{correct/total:.4f}"
        })
    
    return {
        "loss": total_loss / total,
        "accuracy": correct / total
    }


def validate(
    model: nn.Module,
    dataloader: DataLoader,
    criterion: nn.Module,
    device: torch.device,
    epoch: int
) -> dict:
    """
    验证
    """
    model.eval()
    total_loss = 0.0
    correct = 0
    total = 0
    
    # 分质量统计
    quality_correct = {"good": 0, "medium": 0, "poor": 0}
    quality_total = {"good": 0, "medium": 0, "poor": 0}
    
    pbar = tqdm(dataloader, desc=f"Epoch {epoch} [Val]")
    
    with torch.no_grad():
        for batch in pbar:
            template = batch["template"].to(device)
            sample = batch["sample"].to(device)
            target = batch["target"].to(device)
            qualities = batch["quality"]
            
            # 前向传播
            feat1, feat2 = model(template, sample)
            loss = criterion(feat1, feat2, target)
            
            # 统计
            total_loss += loss.item() * template.size(0)
            
            similarity = (feat1 * feat2).sum(dim=1)
            pred_positive = similarity > 0
            target_positive = target > 0
            batch_correct = (pred_positive == target_positive).sum().item()
            correct += batch_correct
            total += template.size(0)
            
            # 分质量统计
            for i, q in enumerate(qualities):
                quality_total[q] += 1
                if (pred_positive[i] == target_positive[i]):
                    quality_correct[q] += 1
            
            pbar.set_postfix({
                "loss": f"{loss.item():.4f}",
                "acc": f"{correct/total:.4f}"
            })
    
    # 打印分质量准确率
    for q in ["good", "medium", "poor"]:
        if quality_total[q] > 0:
            logger.info(f"  {q}: {quality_correct[q]}/{quality_total[q]} = {quality_correct[q]/quality_total[q]:.4f}")
    
    return {
        "loss": total_loss / total,
        "accuracy": correct / total
    }


def export_onnx(
    model: nn.Module,
    output_path: Path,
    opset_version: int = 11
):
    """
    导出 ONNX 模型
    
    Args:
        model: 训练好的模型
        output_path: 输出路径
        opset_version: ONNX opset 版本
    """
    model.eval()
    device = next(model.parameters()).device
    
    # 创建示例输入
    dummy_input1 = torch.randn(1, 1, 224, 224).to(device)
    dummy_input2 = torch.randn(1, 1, 224, 224).to(device)
    
    # 导出
    torch.onnx.export(
        model,
        (dummy_input1, dummy_input2),
        str(output_path),
        opset_version=opset_version,
        input_names=["input1", "input2"],
        output_names=["feature1", "feature2"],
        dynamic_axes=None,  # 固定尺寸
        do_constant_folding=True,
        verbose=False
    )
    
    logger.info(f"✅ ONNX 模型已导出: {output_path}")
    
    # 验证导出
    import onnx
    onnx_model = onnx.load(str(output_path))
    onnx.checker.check_model(onnx_model)
    logger.info("✅ ONNX 模型验证通过")


def train(
    data_dir: Path = None,
    output_dir: Path = None,
    epochs: int = 50,
    batch_size: int = 32,
    learning_rate: float = 1e-4,
    weight_decay: float = 1e-5,
    pretrained: bool = False,
    seed: int = 42,
    device: str = None
):
    """
    训练主函数
    """
    # 设置随机种子
    torch.manual_seed(seed)
    np.random.seed(seed)
    random.seed(seed)
    
    # 设备
    if device is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"
    device = torch.device(device)
    logger.info(f"🎯 使用设备: {device}")
    
    # 路径
    if data_dir is None:
        data_dir = DATA_DIR
    if output_dir is None:
        output_dir = OUTPUT_DIR
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 数据变换
    transform = transforms.Compose([
        transforms.ToTensor(),  # 自动归一化到 [0, 1]
    ])
    
    # 创建数据集
    train_dataset = SiameseDataset(
        data_dir=data_dir,
        transform=transform,
        split="train",
        seed=seed
    )
    
    val_dataset = SiameseDataset(
        data_dir=data_dir,
        transform=transform,
        split="val",
        seed=seed
    )
    
    # 创建数据加载器
    train_loader = DataLoader(
        train_dataset,
        batch_size=batch_size,
        shuffle=True,
        num_workers=4,
        pin_memory=True
    )
    
    val_loader = DataLoader(
        val_dataset,
        batch_size=batch_size,
        shuffle=False,
        num_workers=4,
        pin_memory=True
    )
    
    # 创建模型
    model = SiameseNet(pretrained=pretrained).to(device)
    logger.info(f"📦 模型参数: {sum(p.numel() for p in model.parameters()):,}")
    
    # 损失函数
    criterion = nn.CosineEmbeddingLoss(margin=0.0)
    
    # 优化器
    optimizer = torch.optim.Adam(
        model.parameters(),
        lr=learning_rate,
        weight_decay=weight_decay
    )
    
    # 学习率调度器
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
        optimizer,
        T_max=epochs,
        eta_min=1e-6
    )
    
    # 训练循环
    best_val_loss = float("inf")
    history = {"train_loss": [], "train_acc": [], "val_loss": [], "val_acc": []}
    
    logger.info("=" * 60)
    logger.info("🚀 开始训练")
    logger.info("=" * 60)
    logger.info(f"训练样本: {len(train_dataset)}")
    logger.info(f"验证样本: {len(val_dataset)}")
    logger.info(f"Epochs: {epochs}")
    logger.info(f"Batch Size: {batch_size}")
    logger.info(f"Learning Rate: {learning_rate}")
    logger.info("=" * 60)
    
    for epoch in range(1, epochs + 1):
        # 训练
        train_metrics = train_one_epoch(
            model, train_loader, criterion, optimizer, device, epoch
        )
        
        # 验证
        val_metrics = validate(
            model, val_loader, criterion, device, epoch
        )
        
        # 更新学习率
        scheduler.step()
        
        # 记录历史
        history["train_loss"].append(train_metrics["loss"])
        history["train_acc"].append(train_metrics["accuracy"])
        history["val_loss"].append(val_metrics["loss"])
        history["val_acc"].append(val_metrics["accuracy"])
        
        # 打印摘要
        logger.info(
            f"Epoch {epoch}/{epochs} - "
            f"Train Loss: {train_metrics['loss']:.4f}, Acc: {train_metrics['accuracy']:.4f} | "
            f"Val Loss: {val_metrics['loss']:.4f}, Acc: {val_metrics['accuracy']:.4f} | "
            f"LR: {scheduler.get_last_lr()[0]:.6f}"
        )
        
        # 保存最佳模型
        if val_metrics["loss"] < best_val_loss:
            best_val_loss = val_metrics["loss"]
            
            # 保存 PyTorch 权重
            checkpoint_path = output_dir / "siamese_calligraphy_best.pth"
            torch.save({
                "epoch": epoch,
                "model_state_dict": model.state_dict(),
                "optimizer_state_dict": optimizer.state_dict(),
                "val_loss": val_metrics["loss"],
                "val_acc": val_metrics["accuracy"],
            }, checkpoint_path)
            logger.info(f"  💾 保存最佳模型: {checkpoint_path}")
    
    # 保存最终模型
    final_path = output_dir / "siamese_calligraphy_final.pth"
    torch.save({
        "epoch": epochs,
        "model_state_dict": model.state_dict(),
        "optimizer_state_dict": optimizer.state_dict(),
        "history": history,
    }, final_path)
    logger.info(f"💾 保存最终模型: {final_path}")
    
    # 导出 ONNX
    onnx_path = output_dir / "siamese_calligraphy.onnx"
    export_onnx(model, onnx_path)
    
    # 保存训练历史
    import json
    history_path = output_dir / "training_history.json"
    with open(history_path, "w") as f:
        json.dump(history, f, indent=2)
    logger.info(f"💾 保存训练历史: {history_path}")
    
    logger.info("=" * 60)
    logger.info("✅ 训练完成!")
    logger.info("=" * 60)
    
    return model, history


def main():
    parser = argparse.ArgumentParser(description="InkPi 孪生网络训练")
    parser.add_argument("--data", "-d", type=str, default=str(DATA_DIR), help="数据目录")
    parser.add_argument("--output", "-o", type=str, default=str(OUTPUT_DIR), help="输出目录")
    parser.add_argument("--epochs", "-e", type=int, default=50, help="训练轮数")
    parser.add_argument("--batch-size", "-b", type=int, default=32, help="批大小")
    parser.add_argument("--lr", type=float, default=1e-4, help="学习率")
    parser.add_argument("--weight-decay", type=float, default=1e-5, help="权重衰减")
    parser.add_argument("--pretrained", action="store_true", help="使用预训练权重")
    parser.add_argument("--seed", type=int, default=42, help="随机种子")
    parser.add_argument("--device", type=str, default=None, help="设备 (cuda/cpu)")
    
    args = parser.parse_args()
    
    train(
        data_dir=Path(args.data),
        output_dir=Path(args.output),
        epochs=args.epochs,
        batch_size=args.batch_size,
        learning_rate=args.lr,
        weight_decay=args.weight_decay,
        pretrained=args.pretrained,
        seed=args.seed,
        device=args.device
    )


if __name__ == "__main__":
    main()