"""Shared script and artifact layout helpers for quality scorer training."""

from __future__ import annotations

from pathlib import Path


SUPPORTED_SCRIPTS = ("regular", "running")
DEFAULT_SCRIPT = "regular"
ALL_SCRIPTS = "all"

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PUBLIC_CHARACTER_ROOT = PROJECT_ROOT / "data" / "public_character"
DEFAULT_MANIFEST_ROOT = PROJECT_ROOT / "data" / "quality_manifests"
DEFAULT_MODEL_ROOT = PROJECT_ROOT / "models"


def normalize_script(script: str) -> str:
    normalized = (script or "").strip().lower()
    if normalized in SUPPORTED_SCRIPTS:
        return normalized
    raise ValueError(f"Unsupported script '{script}'. Expected one of: {', '.join(SUPPORTED_SCRIPTS)}.")


def normalize_script_target(script: str) -> str:
    normalized = (script or "").strip().lower()
    if normalized == ALL_SCRIPTS:
        return normalized
    return normalize_script(normalized)


def resolve_script_source_dir(public_character_root: Path, script: str) -> Path:
    script = normalize_script(script)
    root = Path(public_character_root)
    nested_dir = root / script
    if nested_dir.is_dir():
        return nested_dir
    return root


def build_manifest_path(manifest_root: Path, script: str) -> Path:
    script = normalize_script(script)
    return Path(manifest_root) / script / "quality_manifest.jsonl"


def build_model_paths(model_root: Path, script: str) -> dict[str, Path]:
    script = normalize_script(script)
    root = Path(model_root)
    artifact_dir = root
    return {
        "artifact_dir": artifact_dir,
        "onnx_path": artifact_dir / f"quality_scorer_{script}.onnx",
        "metrics_path": artifact_dir / f"quality_scorer_{script}.metrics.json",
    }
