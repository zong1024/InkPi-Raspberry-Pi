from __future__ import annotations

import argparse
import json
import logging
import random
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

import cv2
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader, Dataset
from torchvision.models import MobileNet_V3_Small_Weights, mobilenet_v3_small
from tqdm import tqdm

try:
    from torch.amp import GradScaler, autocast

    def make_grad_scaler(enabled: bool):
        return GradScaler("cuda", enabled=enabled)

    def autocast_context(enabled: bool):
        return autocast("cuda", enabled=enabled)

except ImportError:
    from torch.cuda.amp import GradScaler, autocast  # type: ignore

    def make_grad_scaler(enabled: bool):
        return GradScaler(enabled=enabled)

    def autocast_context(enabled: bool):
        return autocast(enabled=enabled)


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATA_DIR = PROJECT_ROOT / "data" / "synthetic"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "models"
QUALITY_LEVELS = ("good", "medium", "poor")
QUALITY_FILENAME_PATTERN = re.compile(
    r"^(?P<char>.+?)_(?P<quality>good|medium|poor)_(?P<index>\d+)$"
)


@dataclass
class SampleItem:
    template_path: Path
    sample_path: Path
    quality: str
    char: str


@dataclass
class PairItem:
    template_path: Path
    sample_path: Path
    target: float
    quality: str
    char: str
    pair_type: str


@dataclass
class DatasetAudit:
    total_templates: int
    total_samples: int
    matched_samples: int
    unmatched_samples: int
    matched_ratio: float
    unique_chars: int
    quality_counts: Dict[str, int]
    matched_quality_counts: Dict[str, int]
    unmatched_examples: List[str]


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
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


def parse_sample_character(sample_path: Path) -> tuple[str | None, str | None]:
    match = QUALITY_FILENAME_PATTERN.match(sample_path.stem)
    if match:
        return match.group("char"), match.group("quality")

    parts = sample_path.stem.split("_")
    if len(parts) >= 3 and parts[-2] in QUALITY_LEVELS:
        return "_".join(parts[:-2]), parts[-2]

    return None, None


def audit_dataset_dir(data_dir: Path) -> DatasetAudit:
    data_dir = Path(data_dir)
    templates = {p.stem: p for p in (data_dir / "originals").glob("*.png")}

    total_samples = 0
    matched_samples = 0
    quality_counts = {quality: 0 for quality in QUALITY_LEVELS}
    matched_quality_counts = {quality: 0 for quality in QUALITY_LEVELS}
    matched_chars = set()
    unmatched_examples: List[str] = []

    for quality in QUALITY_LEVELS:
        q_dir = data_dir / quality
        if not q_dir.exists():
            continue

        for sample_path in q_dir.glob("*.png"):
            total_samples += 1
            quality_counts[quality] += 1

            char_name, parsed_quality = parse_sample_character(sample_path)
            if parsed_quality not in QUALITY_LEVELS:
                if len(unmatched_examples) < 10:
                    unmatched_examples.append(sample_path.name)
                continue

            if char_name in templates:
                matched_samples += 1
                matched_quality_counts[quality] += 1
                matched_chars.add(char_name)
            elif len(unmatched_examples) < 10:
                unmatched_examples.append(sample_path.name)

    unmatched_samples = total_samples - matched_samples
    matched_ratio = matched_samples / total_samples if total_samples else 0.0

    return DatasetAudit(
        total_templates=len(templates),
        total_samples=total_samples,
        matched_samples=matched_samples,
        unmatched_samples=unmatched_samples,
        matched_ratio=matched_ratio,
        unique_chars=len(matched_chars),
        quality_counts=quality_counts,
        matched_quality_counts=matched_quality_counts,
        unmatched_examples=unmatched_examples,
    )


class SiameseDataset(Dataset):
    def __init__(
        self,
        data_dir: Path,
        split: str = "train",
        train_ratio: float = 0.8,
        seed: int = 42,
        image_size: int = 224,
        negative_ratio: int = 1,
    ):
        self.data_dir = Path(data_dir)
        self.split = split
        self.image_size = image_size
        self.negative_ratio = max(0, int(negative_ratio))
        self.unmatched_examples: List[str] = []

        self.templates = {p.stem: p for p in (self.data_dir / "originals").glob("*.png")}

        all_samples: List[SampleItem] = []
        for quality in QUALITY_LEVELS:
            q_dir = self.data_dir / quality
            if not q_dir.exists():
                continue

            for sample_path in q_dir.glob("*.png"):
                char_name, parsed_quality = parse_sample_character(sample_path)
                template_path = self.templates.get(char_name) if char_name else None
                if char_name and template_path and parsed_quality == quality:
                    all_samples.append(
                        SampleItem(
                            template_path=template_path,
                            sample_path=sample_path,
                            quality=quality,
                            char=char_name,
                        )
                    )
                elif len(self.unmatched_examples) < 10:
                    self.unmatched_examples.append(sample_path.name)

        rng = random.Random(seed)
        rng.shuffle(all_samples)
        split_idx = int(len(all_samples) * train_ratio)

        if split == "train":
            self.samples = all_samples[:split_idx]
        elif split == "val":
            self.samples = all_samples[split_idx:]
        else:
            raise ValueError(f"Unknown split: {split}")

        self.pairs = self._build_pairs(seed + (0 if split == "train" else 10_000))
        logger.info(
            "[%s] matched_samples=%d, pairs=%d, unique_chars=%d",
            split,
            len(self.samples),
            len(self.pairs),
            len({sample.char for sample in self.samples}),
        )

    def _build_pairs(self, seed: int) -> List[PairItem]:
        rng = random.Random(seed)
        pairs: List[PairItem] = []
        samples_by_char: Dict[str, List[SampleItem]] = {}

        for sample in self.samples:
            samples_by_char.setdefault(sample.char, []).append(sample)
            pairs.append(
                PairItem(
                    template_path=sample.template_path,
                    sample_path=sample.sample_path,
                    target=1.0,
                    quality=sample.quality,
                    char=sample.char,
                    pair_type="positive",
                )
            )

        chars = list(samples_by_char.keys())
        if len(chars) < 2 or self.negative_ratio <= 0:
            return pairs

        for sample in self.samples:
            other_chars = [char for char in chars if char != sample.char]
            for _ in range(self.negative_ratio):
                negative_char = rng.choice(other_chars)
                negative_sample = rng.choice(samples_by_char[negative_char])
                pairs.append(
                    PairItem(
                        template_path=sample.template_path,
                        sample_path=negative_sample.sample_path,
                        target=-1.0,
                        quality=negative_sample.quality,
                        char=sample.char,
                        pair_type="negative",
                    )
                )

        rng.shuffle(pairs)
        return pairs

    def __len__(self) -> int:
        return len(self.pairs)

    def _load_gray(self, path: Path) -> np.ndarray:
        image = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
        if image is None:
            raise ValueError(f"Failed to read image: {path}")
        image = cv2.resize(image, (self.image_size, self.image_size), interpolation=cv2.INTER_AREA)
        return image.astype(np.float32) / 255.0

    def __getitem__(self, idx: int) -> Dict[str, torch.Tensor]:
        item = self.pairs[idx]
        template = torch.from_numpy(self._load_gray(item.template_path)).unsqueeze(0)
        sample = torch.from_numpy(self._load_gray(item.sample_path)).unsqueeze(0)
        return {
            "template": template,
            "sample": sample,
            "target": torch.tensor(item.target, dtype=torch.float32),
            "quality": item.quality,
            "char": item.char,
            "pair_type": item.pair_type,
        }


class SiameseNet(nn.Module):
    def __init__(self, pretrained: bool = False, embedding_dim: int = 128):
        super().__init__()

        weights = MobileNet_V3_Small_Weights.DEFAULT if pretrained else None
        backbone = mobilenet_v3_small(weights=weights)

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

        backbone.classifier = nn.Sequential(
            nn.Linear(576, 256),
            nn.Hardswish(inplace=True),
            nn.Dropout(0.2),
            nn.Linear(256, embedding_dim),
        )
        self.backbone = backbone

    def forward_one(self, x: torch.Tensor) -> torch.Tensor:
        features = self.backbone(x)
        return F.normalize(features, p=2, dim=1)

    def forward(self, x1: torch.Tensor, x2: torch.Tensor):
        return self.forward_one(x1), self.forward_one(x2)


def compute_sign_acc(feat1: torch.Tensor, feat2: torch.Tensor, target: torch.Tensor) -> float:
    similarity = (feat1 * feat2).sum(dim=1)
    predictions = torch.where(similarity >= 0, 1.0, -1.0)
    return (predictions == target).float().mean().item()


def train_one_epoch(
    model: nn.Module,
    loader: DataLoader,
    criterion: nn.Module,
    optimizer: torch.optim.Optimizer,
    device: torch.device,
    scaler,
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
        if use_amp:
            with autocast_context(True):
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

        batch_size = x1.size(0)
        acc = compute_sign_acc(f1.detach(), f2.detach(), y.detach())
        total_loss += loss.item() * batch_size
        total_acc += acc * batch_size
        total_n += batch_size
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

        batch_size = x1.size(0)
        total_loss += loss.item() * batch_size
        total_acc += acc * batch_size
        total_n += batch_size
        pbar.set_postfix(loss=f"{loss.item():.4f}", acc=f"{acc:.4f}")

    return {
        "loss": total_loss / max(total_n, 1),
        "accuracy": total_acc / max(total_n, 1),
    }


def export_onnx(model: nn.Module, output_path: Path, image_size: int, device: torch.device) -> None:
    model.eval()
    dummy1 = torch.randn(1, 1, image_size, image_size, device=device)
    dummy2 = torch.randn(1, 1, image_size, image_size, device=device)
    torch.onnx.export(
        model,
        (dummy1, dummy2),
        str(output_path),
        opset_version=11,
        input_names=["input1", "input2"],
        output_names=["feature1", "feature2"],
        dynamic_axes={
            "input1": {0: "batch_size"},
            "input2": {0: "batch_size"},
            "feature1": {0: "batch_size"},
            "feature2": {0: "batch_size"},
        },
        do_constant_folding=True,
    )
    logger.info("ONNX export complete: %s", output_path)


def check_dataset_or_raise(
    data_dir: Path,
    min_match_ratio: float,
    min_matched_samples: int,
    allow_partial_dataset: bool,
) -> DatasetAudit:
    logger.info("Dataset directory: %s", data_dir.resolve())
    if not data_dir.exists():
        raise FileNotFoundError(f"Dataset directory does not exist: {data_dir}")

    audit = audit_dataset_dir(data_dir)
    logger.info("  templates: %d", audit.total_templates)
    for quality in QUALITY_LEVELS:
        logger.info(
            "  %s: raw=%d matched=%d",
            quality,
            audit.quality_counts[quality],
            audit.matched_quality_counts[quality],
        )
    logger.info(
        "  matched=%d unmatched=%d ratio=%.2f%% unique_chars=%d",
        audit.matched_samples,
        audit.unmatched_samples,
        audit.matched_ratio * 100,
        audit.unique_chars,
    )

    if audit.total_templates == 0:
        raise ValueError("No template images found in originals/.")
    if audit.matched_samples == 0:
        raise ValueError(
            "No character-labeled training samples matched the templates. "
            "Check that filenames follow <char>_<quality>_<index>.png and that originals/<char>.png exists."
        )
    if audit.unique_chars < 2:
        raise ValueError("At least 2 distinct characters are required to build negative pairs.")

    problems: List[str] = []
    if audit.matched_samples < min_matched_samples:
        problems.append(
            f"only {audit.matched_samples} matched samples were usable (minimum recommended: {min_matched_samples})"
        )
    if audit.matched_ratio < min_match_ratio:
        problems.append(
            f"only {audit.matched_ratio:.2%} of the files matched a template label (minimum recommended: {min_match_ratio:.0%})"
        )

    if problems and not allow_partial_dataset:
        examples = ", ".join(audit.unmatched_examples[:5]) if audit.unmatched_examples else "none"
        raise ValueError(
            "Dataset audit failed: "
            + "; ".join(problems)
            + f". Example unmatched files: {examples}. "
            + "If this came from the GitHub style dataset, it is style-labeled rather than character-labeled "
            + "and is not suitable for Siamese character matching."
        )

    if problems:
        logger.warning("Proceeding with partial dataset because --allow-partial-dataset was set.")
        for problem in problems:
            logger.warning("  %s", problem)

    return audit


def train(args: argparse.Namespace) -> None:
    set_seed(args.seed)
    data_dir = Path(args.data)
    output_dir = Path(args.output)
    safe_mkdir(output_dir)

    device = resolve_device(args.device)
    logger.info("Device: %s", device)
    if device.type == "cuda":
        torch.backends.cudnn.benchmark = True
        logger.info("GPU: %s", torch.cuda.get_device_name(0))

    audit = check_dataset_or_raise(
        data_dir=data_dir,
        min_match_ratio=args.min_match_ratio,
        min_matched_samples=args.min_matched_samples,
        allow_partial_dataset=args.allow_partial_dataset,
    )

    train_ds = SiameseDataset(
        data_dir=data_dir,
        split="train",
        train_ratio=args.train_ratio,
        seed=args.seed,
        image_size=args.image_size,
        negative_ratio=args.negative_ratio,
    )
    val_ds = SiameseDataset(
        data_dir=data_dir,
        split="val",
        train_ratio=args.train_ratio,
        seed=args.seed,
        image_size=args.image_size,
        negative_ratio=args.negative_ratio,
    )

    if len(train_ds) == 0:
        raise ValueError("Training set is empty after pair construction.")
    if len(val_ds) == 0:
        raise ValueError("Validation set is empty after pair construction.")

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
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
        optimizer, T_max=args.epochs, eta_min=1e-6
    )

    use_amp = bool(args.amp and device.type == "cuda")
    scaler = make_grad_scaler(use_amp)

    logger.info(
        "Start training: matched_samples=%d train_pairs=%d val_pairs=%d batch=%d epochs=%d",
        audit.matched_samples,
        len(train_ds),
        len(val_ds),
        args.batch_size,
        args.epochs,
    )

    history = {
        "train_loss": [],
        "train_acc": [],
        "val_loss": [],
        "val_acc": [],
        "lr": [],
        "matched_samples": audit.matched_samples,
        "matched_ratio": audit.matched_ratio,
        "unique_chars": audit.unique_chars,
    }

    best_val_loss = float("inf")
    best_path = output_dir / "siamese_calligraphy_best.pth"
    final_path = output_dir / "siamese_calligraphy_final.pth"
    history_path = output_dir / "training_history.json"
    onnx_path = output_dir / "siamese_calligraphy.onnx"

    for epoch in range(1, args.epochs + 1):
        train_metrics = train_one_epoch(
            model, train_loader, criterion, optimizer, device, scaler, use_amp
        )
        val_metrics = validate_one_epoch(model, val_loader, criterion, device)
        scheduler.step()

        current_lr = optimizer.param_groups[0]["lr"]
        history["train_loss"].append(train_metrics["loss"])
        history["train_acc"].append(train_metrics["accuracy"])
        history["val_loss"].append(val_metrics["loss"])
        history["val_acc"].append(val_metrics["accuracy"])
        history["lr"].append(current_lr)

        logger.info(
            "Epoch %d/%d | train_loss=%.4f train_acc=%.4f | val_loss=%.4f val_acc=%.4f | lr=%.6f",
            epoch,
            args.epochs,
            train_metrics["loss"],
            train_metrics["accuracy"],
            val_metrics["loss"],
            val_metrics["accuracy"],
            current_lr,
        )

        if val_metrics["loss"] < best_val_loss:
            best_val_loss = val_metrics["loss"]
            torch.save(
                {
                    "epoch": epoch,
                    "model_state_dict": model.state_dict(),
                    "optimizer_state_dict": optimizer.state_dict(),
                    "val_loss": val_metrics["loss"],
                    "val_acc": val_metrics["accuracy"],
                    "args": vars(args),
                    "dataset_audit": audit.__dict__,
                },
                best_path,
            )
            logger.info("Saved best checkpoint: %s", best_path)

    torch.save(
        {
            "epoch": args.epochs,
            "model_state_dict": model.state_dict(),
            "optimizer_state_dict": optimizer.state_dict(),
            "history": history,
            "args": vars(args),
            "dataset_audit": audit.__dict__,
        },
        final_path,
    )
    logger.info("Saved final checkpoint: %s", final_path)

    with open(history_path, "w", encoding="utf-8") as handle:
        json.dump(history, handle, ensure_ascii=False, indent=2)
    logger.info("Saved history: %s", history_path)

    export_onnx(model, onnx_path, args.image_size, device)
    logger.info("Training complete")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Train the InkPi Siamese matching model.")
    parser.add_argument("--data", type=str, default=str(DEFAULT_DATA_DIR), help="Dataset directory")
    parser.add_argument("--output", type=str, default=str(DEFAULT_OUTPUT_DIR), help="Output directory")
    parser.add_argument("--epochs", type=int, default=50, help="Epoch count")
    parser.add_argument("--batch-size", type=int, default=64, help="Batch size")
    parser.add_argument("--lr", type=float, default=1e-4, help="Learning rate")
    parser.add_argument("--weight-decay", type=float, default=1e-5, help="Weight decay")
    parser.add_argument("--margin", type=float, default=0.0, help="Cosine embedding margin")
    parser.add_argument("--train-ratio", type=float, default=0.8, help="Train/val split ratio")
    parser.add_argument("--image-size", type=int, default=224, help="Input image size")
    parser.add_argument("--embedding-dim", type=int, default=128, help="Embedding dimension")
    parser.add_argument("--workers", type=int, default=4, help="DataLoader workers")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--device", type=str, default=None, help="cuda/cpu")
    parser.add_argument("--pretrained", action="store_true", help="Use ImageNet pretrained weights")
    parser.add_argument("--amp", action="store_true", help="Enable AMP on CUDA")
    parser.add_argument("--negative-ratio", type=int, default=1, help="Number of negative pairs per positive pair")
    parser.add_argument(
        "--min-match-ratio",
        type=float,
        default=0.5,
        help="Minimum acceptable matched-file ratio before training aborts",
    )
    parser.add_argument(
        "--min-matched-samples",
        type=int,
        default=100,
        help="Minimum recommended matched sample count before training aborts",
    )
    parser.add_argument(
        "--allow-partial-dataset",
        action="store_true",
        help="Bypass the dataset audit guardrail and train on the matched subset only",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    train(args)


if __name__ == "__main__":
    main()
