"""Train and export a script-aware single-image quality scorer for InkPi."""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import sys

import cv2
import numpy as np

try:
    from training.quality_model_layout import (
        DEFAULT_MANIFEST_ROOT,
        DEFAULT_MODEL_ROOT,
        DEFAULT_SCRIPT,
        build_manifest_path,
        build_model_paths,
        normalize_script,
    )
except ModuleNotFoundError:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from training.quality_model_layout import (
        DEFAULT_MANIFEST_ROOT,
        DEFAULT_MODEL_ROOT,
        DEFAULT_SCRIPT,
        build_manifest_path,
        build_model_paths,
        normalize_script,
    )


LABEL_TO_INDEX = {"bad": 0, "medium": 1, "good": 2}
INDEX_TO_LABEL = {value: key for key, value in LABEL_TO_INDEX.items()}


def load_manifest(path: Path) -> list[dict]:
    samples = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        samples.append(json.loads(line))
    return samples


def encode_character(value: str) -> float:
    if not value:
        return 0.0
    return min(float(ord(value[0])) / 65535.0, 1.0)


def build_features(path: Path, character: str, input_size: int) -> np.ndarray | None:
    image = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    if image is None:
        return None
    resized = cv2.resize(image, (input_size, input_size), interpolation=cv2.INTER_AREA)
    normalized = resized.astype(np.float32) / 255.0
    flat = normalized.reshape(-1)
    char_code = np.asarray([encode_character(character)], dtype=np.float32)
    extras = extract_quality_features(resized)
    return np.concatenate([flat, char_code, extras], axis=0)


def extract_quality_features(image: np.ndarray) -> np.ndarray:
    normalized = cv2.normalize(image, None, 0, 255, cv2.NORM_MINMAX)
    if float(np.mean(normalized)) < 127:
        normalized = 255 - normalized

    _, binary = cv2.threshold(normalized, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    points = cv2.findNonZero(binary)
    h_img, w_img = binary.shape
    if points is None:
        return np.zeros(6, dtype=np.float32)

    x, y, w, h = cv2.boundingRect(points)
    bbox_area = max(1.0, float(w * h))
    image_area = max(1.0, float(h_img * w_img))
    fg_ratio = float(np.mean(binary > 0))
    bbox_ratio = bbox_area / image_area

    moments = cv2.moments(binary)
    if moments["m00"] > 0:
        cx = moments["m10"] / moments["m00"]
        cy = moments["m01"] / moments["m00"]
    else:
        cx = w_img / 2.0
        cy = h_img / 2.0
    center_distance = float(
        np.hypot((cx - w_img / 2.0) / max(1.0, w_img / 2.0), (cy - h_img / 2.0) / max(1.0, h_img / 2.0))
    )

    component_count = max(0, cv2.connectedComponents(binary)[0] - 1)
    edge_touch = float(
        np.mean(binary[0, :] > 0)
        + np.mean(binary[-1, :] > 0)
        + np.mean(binary[:, 0] > 0)
        + np.mean(binary[:, -1] > 0)
    ) / 4.0

    features = np.asarray(
        [
            fg_ratio,
            bbox_ratio,
            max(0.0, 1.0 - center_distance),
            min(component_count / 24.0, 1.0),
            edge_touch,
            float(np.std(normalized.astype(np.float32) / 255.0)),
        ],
        dtype=np.float32,
    )
    return features


def load_dataset(manifest_path: Path, input_size: int, script: str) -> tuple[np.ndarray, np.ndarray, list[dict]]:
    samples = load_manifest(manifest_path)
    features = []
    labels = []
    kept = []
    for sample in samples:
        sample_script = sample.get("script")
        if sample_script and sample_script != script:
            continue
        path = Path(sample["path"])
        feature = build_features(path, sample.get("character", ""), input_size=input_size)
        if feature is None:
            continue
        label = sample.get("label")
        if label not in LABEL_TO_INDEX:
            continue
        features.append(feature)
        labels.append(LABEL_TO_INDEX[label])
        kept.append(sample)

    if not features:
        raise ValueError("No usable samples found in manifest.")

    return np.asarray(features, dtype=np.float32), np.asarray(labels, dtype=np.int64), kept


def probability_score(probabilities: np.ndarray) -> np.ndarray:
    weights = np.asarray([56.0, 76.0, 92.0], dtype=np.float32)
    return probabilities @ weights


def train_model(
    manifest_path: Path,
    output_dir: Path,
    input_size: int,
    hidden1: int,
    hidden2: int,
    max_iter: int,
    test_size: float,
    script: str,
) -> dict:
    from sklearn.metrics import classification_report
    from sklearn.model_selection import train_test_split
    from sklearn.neural_network import MLPClassifier
    from skl2onnx import to_onnx
    from skl2onnx.common.data_types import FloatTensorType

    script = normalize_script(script)
    X, y, kept_samples = load_dataset(manifest_path, input_size=input_size, script=script)

    X_train, X_val, y_train, y_val = train_test_split(
        X,
        y,
        test_size=test_size,
        random_state=42,
        stratify=y,
    )

    model = MLPClassifier(
        hidden_layer_sizes=(hidden1, hidden2),
        activation="relu",
        solver="adam",
        alpha=1e-4,
        batch_size=256,
        learning_rate_init=1e-3,
        max_iter=max_iter,
        early_stopping=True,
        n_iter_no_change=6,
        verbose=True,
        random_state=42,
    )
    model.fit(X_train, y_train)

    train_probs = model.predict_proba(X_train)
    val_probs = model.predict_proba(X_val)
    train_pred = np.argmax(train_probs, axis=1)
    val_pred = np.argmax(val_probs, axis=1)

    train_scores = probability_score(train_probs)
    val_scores = probability_score(val_probs)

    paths = build_model_paths(output_dir, script)
    artifact_dir = paths["artifact_dir"]
    artifact_dir.mkdir(parents=True, exist_ok=True)
    onnx_path = paths["onnx_path"]
    onnx_model = to_onnx(
        model,
        initial_types=[("input", FloatTensorType([None, X.shape[1]]))],
        options={id(model): {"zipmap": False}},
        target_opset=17,
    )
    onnx_path.write_bytes(onnx_model.SerializeToString())

    metrics = {
        "script": script,
        "manifest": str(manifest_path),
        "output_dir": str(artifact_dir),
        "input_size": input_size,
        "feature_dim": int(X.shape[1]),
        "sample_count": int(len(kept_samples)),
        "rubric_families": dict(Counter(sample.get("rubric_family") for sample in kept_samples if sample.get("rubric_family"))),
        "rubric_versions": dict(Counter(sample.get("rubric_version") for sample in kept_samples if sample.get("rubric_version"))),
        "samples_with_rubric_items": int(sum(1 for sample in kept_samples if sample.get("rubric_items"))),
        "manual_review_labeled": int(sum(1 for sample in kept_samples if sample.get("manual_review_score") is not None)),
        "label_counts": {INDEX_TO_LABEL[int(label)]: int(count) for label, count in Counter(y).items()},
        "train_accuracy": float(np.mean(train_pred == y_train)),
        "val_accuracy": float(np.mean(val_pred == y_val)),
        "train_score_mean": float(np.mean(train_scores)),
        "val_score_mean": float(np.mean(val_scores)),
        "per_label_val_score_mean": {
            INDEX_TO_LABEL[index]: float(np.mean(val_scores[y_val == index])) for index in sorted(np.unique(y_val))
        },
        "classification_report": classification_report(
            y_val,
            val_pred,
            target_names=[INDEX_TO_LABEL[index] for index in range(len(LABEL_TO_INDEX))],
            output_dict=True,
            zero_division=0,
        ),
        "onnx_path": str(onnx_path),
    }
    paths["metrics_path"].write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser(description="Train a script-specific InkPi quality scorer and export ONNX.")
    parser.add_argument(
        "--script",
        type=str,
        default=DEFAULT_SCRIPT,
        help="Script bucket to train: regular or running.",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=None,
        help="Input manifest path. Defaults to data/quality_manifests/<script>/quality_manifest.jsonl",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_MODEL_ROOT,
        help="Artifact root. Model files will be written to <output-dir>/<script>/",
    )
    parser.add_argument("--input-size", type=int, default=32)
    parser.add_argument("--hidden1", type=int, default=256)
    parser.add_argument("--hidden2", type=int, default=128)
    parser.add_argument("--max-iter", type=int, default=24)
    parser.add_argument("--test-size", type=float, default=0.18)
    args = parser.parse_args()
    script = normalize_script(args.script)
    manifest_path = args.manifest or build_manifest_path(DEFAULT_MANIFEST_ROOT, script)

    metrics = train_model(
        manifest_path=manifest_path,
        output_dir=args.output_dir,
        input_size=args.input_size,
        hidden1=args.hidden1,
        hidden2=args.hidden2,
        max_iter=args.max_iter,
        test_size=args.test_size,
        script=script,
    )
    print(json.dumps(metrics, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
