"""
InkPi 书法评测系统 - 稳定版孪生网络训练脚本

目标：
1. 稳定可训练（优先）
2. 兼容 CPU / 单卡 GPU / V100
3. 数据集检查清晰，错误提示明确
4. 导出 best/final checkpoint + ONNX + history
"""
from __future__ import annotations

import argparse
import json
import logging
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

import cv2
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.cuda.amp import GradScaler, autocast
from torch.utils.data import DataLoader, Dataset
from torchvision.models import MobileNet_V3_Small_Weights, mobilenet_v3_small
from tqdm import tqdm

# =========================
# 基础配置
# =========================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATA_DIR = PROJECT_ROOT / "data" / "synthetic"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "models"

QUALITY_TARGETS = {
    "good": 1.0,
    "medium": 0.3,
    "poor": -1.0,
}


# =========================
# 工具函数
# =========================
def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)


def resolve_device(device_arg: str | None) -> torch.device:
    if device_arg:
        return torch.device(device_arg)
    return torch.device("cuda" if torch.cuda.is_available() else "cpu")


def safe_mkdir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def list_png_count(path: Path) -> int:
    if not path.exists():
        return 0
    return len(list(path.glob("*.png")))


# =========================
# 数据集
# =========================
@dataclass
class SampleItem:
    template_path: Path
    sample_path: Path
    quality: str
    target: float
    char: str


class SiameseDataset(Dataset):
    def __init__(
        self,
        data_dir: Path,
        split: str = "train",
        train_ratio: float = 0.8,
        seed: int = 42,
        image_size: int = 224,
    ):
        self.data_dir = Path(data_dir)
        self.split = split
        self.image_size = image_size

        self.templates: Dict[str, Path] = {}
        originals_dir = self.data_dir / "originals"
        for p in originals_dir.glob("*.png"):
            self.templates[p.stem] = p

        all_samples: List[SampleItem] = []
        for quality, target in QUALITY_TARGETS.items():
            q_dir = self.data_dir / quality
            if not q_dir.exists():
                continue
            for p in q_dir.glob("*.png"):
                # 文件名约定: {char}_{quality}_{idx}.png
                # 例如: 大_good_0001.png, char_0_good_0001.png
                parts = p.stem.split("_")
                
                # 尝试找到匹配的模板
                char = None
                template_path = None
                
                # 方式1: 尝试第一部分作为字符名 (大_good_0001.png -> 大)
                if parts[0] in self.templates:
                    char = parts[0]
                    template_path = self.templates[char]
                # 方式2: 尝试前两部分作为字符名 (char_0_good_0001.png -> char_0)
                elif len(parts) >= 2:
                    potential_char = f"{parts[0]}_{parts[1]}"
                    if potential_char in self.templates:
                        char = potential_char
                        template_path = self.templates[char]
                
                if char and template_path:
                    all_samples.append(
                        SampleItem(
                            template_path=template_path,
                            sample_path=p,
                            quality=quality,
                            target=target,
                            char=char,
                        )
                    )

        random.Random(seed).shuffle(all_samples)
        split_idx = int(len(all_samples) * train_ratio)

        if split == "train":
            self.samples = all_samples[:split_idx]
        elif split == "val":
            self.samples = all_samples[split_idx:]
        else:
            raise ValueError(f"未知 split: {split}")

        logger.info("[%s] 样本数: %d", split, len(self.samples))

    def __len__(self) -> int:
        return len(self.samples)

    def _load_gray(self, path: Path) -> np.ndarray:
        img = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
        if img is None:
            raise ValueError(f"图像读取失败: {path}")
        img = cv2.resize(img, (self.image_size, self.image_size), interpolation=cv2.INTER_AREA)
        img = img.astype(np.float32) / 255.0
        return img

    def __getitem__(self, idx: int) -> Dict[str, torch.Tensor]:
        item = self.samples[idx]
        t = self._load_gray(item.template_path)
        s = self._load_gray(item.sample_path)

        t = torch.from_numpy(t).unsqueeze(0)  # [1,H,W]
        s = torch.from_numpy(s).unsqueeze(0)

        return {
            "template": t,
            "sample": s,
            "target": torch.tensor(item.target, dtype=torch.float32),
            "quality": item.quality,
            "char": item.char,
        }


# =========================
# 模型
# =========================
class SiameseNet(nn.Module):
    def __init__(self, pretrained: bool = False, embedding_dim: int = 128):
        super().__init__()

        if pretrained:
            weights = MobileNet_V3_Small_Weights.DEFAULT
            backbone = mobilenet_v3_small(weights=weights)
        else:
            backbone = mobilenet_v3_small(weights=None)

        # 3通道改1通道
        old_conv = backbone.features[0][0]
        new_conv = nn.Conv2d(
            in_channels=1,
            out_channels=old_conv.out_channels,
            kernel_size=old_conv.kernel_size,
            stride=old_conv.stride,
            padding=old_conv.padding,
            bias=False,
        )
        if pretrained:
            with torch.no_grad():
                new_conv.weight.copy_(old_conv.weight.mean(dim=1, keepdim=True))
        backbone.features[0][0] = new_conv

        # 分类头改 embedding
        backbone.classifier = nn.Sequential(
            nn.Linear(576, 256),
            nn.Hardswish(inplace=True),
            nn.Dropout(0.2),
            nn.Linear(256, embedding_dim),
        )

        self.backbone = backbone

    def forward_one(self, x: torch.Tensor) -> torch.Tensor:
        feat = self.backbone(x)
        return F.normalize(feat, p=2, dim=1)

    def forward(self, x1: torch.Tensor, x2: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        return self.forward_one(x1), self.forward_one(x2)


# =========================
# 训练/验证
# =========================
def compute_sign_acc(feat1: torch.Tensor, feat2: torch.Tensor, target: torch.Tensor) -> float:
    sim = (feat1 * feat2).sum(dim=1)
    pred_pos = sim > 0
    tgt_pos = target > 0
    return (pred_pos == tgt_pos).float().mean().item()


def train_one_epoch(
    model: nn.Module,
    loader: DataLoader,
    criterion: nn.Module,
    optimizer: torch.optim.Optimizer,
    device: torch.device,
    scaler: GradScaler | None,
    use_amp: bool,
) -> Dict[str, float]:
    model.train()
    total_loss = 0.0
    total_acc = 0.0
    total_n = 0

    pbar = tqdm(loader, desc="Train", leave=False)
    for batch in pbar:
        x1 = batch["template"].to(device, non_blocking=True)
        x2 = batch["sample"].to(device, non_blocking=True)
        y = batch["target"].to(device, non_blocking=True)

        optimizer.zero_grad(set_to_none=True)

        if use_amp and scaler is not None:
            with autocast():
                f1, f2 = model(x1, x2)
                loss = criterion(f1, f2, y)
            scaler.scale(loss).backward()
            scaler.step(optimizer)
            scaler.update()
        else:
            f1, f2 = model(x1, x2)
            loss = criterion(f1, f2, y)
            loss.backward()
            optimizer.step()

        bs = x1.size(0)
        acc = compute_sign_acc(f1.detach(), f2.detach(), y.detach())

        total_loss += loss.item() * bs
        total_acc += acc * bs
        total_n += bs

        pbar.set_postfix(loss=f"{loss.item():.4f}", acc=f"{acc:.4f}")

    return {
        "loss": total_loss / max(total_n, 1),
        "accuracy": total_acc / max(total_n, 1),
    }


@torch.no_grad()
def validate_one_epoch(
    model: nn.Module,
    loader: DataLoader,
    criterion: nn.Module,
    device: torch.device,
) -> Dict[str, float]:
    model.eval()
    total_loss = 0.0
    total_acc = 0.0
    total_n = 0

    pbar = tqdm(loader, desc="Val", leave=False)
    for batch in pbar:
        x1 = batch["template"].to(device, non_blocking=True)
        x2 = batch["sample"].to(device, non_blocking=True)
        y = batch["target"].to(device, non_blocking=True)

        f1, f2 = model(x1, x2)
        loss = criterion(f1, f2, y)
        acc = compute_sign_acc(f1, f2, y)

        bs = x1.size(0)
        total_loss += loss.item() * bs
        total_acc += acc * bs
        total_n += bs

        pbar.set_postfix(loss=f"{loss.item():.4f}", acc=f"{acc:.4f}")

    return {
        "loss": total_loss / max(total_n, 1),
        "accuracy": total_acc / max(total_n, 1),
    }


# =========================
# 导出
# =========================
def export_onnx(model: nn.Module, output_path: Path, device: torch.device) -> None:
    model.eval()
    dummy1 = torch.randn(1, 1, 224, 224, device=device)
    dummy2 = torch.randn(1, 1, 224, 224, device=device)

    torch.onnx.export(
        model,
        (dummy1, dummy2),
        str(output_path),
        opset_version=11,
        input_names=["input1", "input2"],
        output_names=["feature1", "feature2"],
        do_constant_folding=True,
    )
    logger.info("✅ ONNX 导出完成: %s", output_path)


# =========================
# 主流程
# =========================
def check_dataset_or_raise(data_dir: Path) -> None:
    logger.info("📁 数据目录: %s", data_dir.resolve())
    if not data_dir.exists():
        raise FileNotFoundError(f"数据目录不存在: {data_dir}")

    originals = list_png_count(data_dir / "originals")
    good = list_png_count(data_dir / "good")
    medium = list_png_count(data_dir / "medium")
    poor = list_png_count(data_dir / "poor")

    logger.info("  originals: %d", originals)
    logger.info("  good: %d", good)
    logger.info("  medium: %d", medium)
    logger.info("  poor: %d", poor)

    if originals == 0:
        raise ValueError("originals 为空，缺少模板图")
    if (good + medium + poor) == 0:
        raise ValueError("训练样本为空，请先生成数据集")


def train(args: argparse.Namespace) -> None:
    set_seed(args.seed)

    data_dir = Path(args.data)
    output_dir = Path(args.output)
    safe_mkdir(output_dir)

    device = resolve_device(args.device)
    logger.info("🎯 设备: %s", device)

    if device.type == "cuda":
        torch.backends.cudnn.benchmark = True
        logger.info("🎮 GPU: %s", torch.cuda.get_device_name(0))

    check_dataset_or_raise(data_dir)

    train_ds = SiameseDataset(
        data_dir=data_dir,
        split="train",
        train_ratio=args.train_ratio,
        seed=args.seed,
        image_size=args.image_size,
    )
    val_ds = SiameseDataset(
        data_dir=data_dir,
        split="val",
        train_ratio=args.train_ratio,
        seed=args.seed,
        image_size=args.image_size,
    )

    if len(train_ds) == 0:
        raise ValueError("训练集为空，无法训练")
    if len(val_ds) == 0:
        raise ValueError("验证集为空，请调整 train_ratio 或数据量")

    train_loader = DataLoader(
        train_ds,
        batch_size=args.batch_size,
        shuffle=True,
        num_workers=args.workers,
        pin_memory=(device.type == "cuda"),
        drop_last=False,
    )
    val_loader = DataLoader(
        val_ds,
        batch_size=args.batch_size,
        shuffle=False,
        num_workers=args.workers,
        pin_memory=(device.type == "cuda"),
        drop_last=False,
    )

    model = SiameseNet(pretrained=args.pretrained, embedding_dim=args.embedding_dim).to(device)
    criterion = nn.CosineEmbeddingLoss(margin=args.margin)
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=args.weight_decay)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=args.epochs, eta_min=1e-6)

    use_amp = bool(args.amp and device.type == "cuda")
    scaler = GradScaler() if use_amp else None

    logger.info("🚀 开始训练")
    logger.info("train=%d, val=%d, batch=%d, epochs=%d", len(train_ds), len(val_ds), args.batch_size, args.epochs)

    history = {
        "train_loss": [],
        "train_acc": [],
        "val_loss": [],
        "val_acc": [],
        "lr": [],
    }

    best_val_loss = float("inf")
    best_path = output_dir / "siamese_calligraphy_best.pth"
    final_path = output_dir / "siamese_calligraphy_final.pth"
    hist_path = output_dir / "training_history.json"
    onnx_path = output_dir / "siamese_calligraphy.onnx"

    for epoch in range(1, args.epochs + 1):
        train_m = train_one_epoch(model, train_loader, criterion, optimizer, device, scaler, use_amp)
        val_m = validate_one_epoch(model, val_loader, criterion, device)
        scheduler.step()

        lr_now = optimizer.param_groups[0]["lr"]
        history["train_loss"].append(train_m["loss"])
        history["train_acc"].append(train_m["accuracy"])
        history["val_loss"].append(val_m["loss"])
        history["val_acc"].append(val_m["accuracy"])
        history["lr"].append(lr_now)

        logger.info(
            "Epoch %d/%d | train_loss=%.4f train_acc=%.4f | val_loss=%.4f val_acc=%.4f | lr=%.6f",
            epoch, args.epochs,
            train_m["loss"], train_m["accuracy"],
            val_m["loss"], val_m["accuracy"],
            lr_now,
        )

        if val_m["loss"] < best_val_loss:
            best_val_loss = val_m["loss"]
            torch.save(
                {
                    "epoch": epoch,
                    "model_state_dict": model.state_dict(),
                    "optimizer_state_dict": optimizer.state_dict(),
                    "val_loss": val_m["loss"],
                    "val_acc": val_m["accuracy"],
                    "args": vars(args),
                },
                best_path,
            )
            logger.info("💾 保存 best: %s", best_path)

    torch.save(
        {
            "epoch": args.epochs,
            "model_state_dict": model.state_dict(),
            "optimizer_state_dict": optimizer.state_dict(),
            "history": history,
            "args": vars(args),
        },
        final_path,
    )
    logger.info("💾 保存 final: %s", final_path)

    with open(hist_path, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)
    logger.info("💾 保存 history: %s", hist_path)

    export_onnx(model, onnx_path, device)
    logger.info("✅ 训练完成")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="InkPi 稳定版孪生网络训练脚本")
    p.add_argument("--data", type=str, default=str(DEFAULT_DATA_DIR), help="数据目录")
    p.add_argument("--output", type=str, default=str(DEFAULT_OUTPUT_DIR), help="输出目录")
    p.add_argument("--epochs", type=int, default=50, help="训练轮数")
    p.add_argument("--batch-size", type=int, default=64, help="批大小")
    p.add_argument("--lr", type=float, default=1e-4, help="学习率")
    p.add_argument("--weight-decay", type=float, default=1e-5, help="权重衰减")
    p.add_argument("--margin", type=float, default=0.0, help="CosineEmbeddingLoss margin")
    p.add_argument("--train-ratio", type=float, default=0.8, help="训练集比例")
    p.add_argument("--image-size", type=int, default=224, help="输入尺寸")
    p.add_argument("--embedding-dim", type=int, default=128, help="特征维度")
    p.add_argument("--workers", type=int, default=4, help="DataLoader workers")
    p.add_argument("--seed", type=int, default=42, help="随机种子")
    p.add_argument("--device", type=str, default=None, help="cuda/cpu")
    p.add_argument("--pretrained", action="store_true", help="使用 ImageNet 预训练")
    p.add_argument("--amp", action="store_true", help="启用 AMP（仅 CUDA）")
    return p


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    train(args)


if __name__ == "__main__":
    main()