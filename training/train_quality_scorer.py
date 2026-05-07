"""Train and export a single-image quality scorer for InkPi."""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path

import cv2
import numpy as np
from sklearn.metrics import classification_report
from sklearn.model_selection import train_test_split
from sklearn.neural_network import MLPClassifier
from skl2onnx import to_onnx
from skl2onnx.common.data_types import FloatTensorType


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


def encode_calligraphy_style(value: str | None) -> float:
    value = str(value or "").strip().lower()
    if value in {"xingshu", "xing", "running", "行书", "行"}:
        return 1.0
    return 0.0


def build_features(path: Path, character: str, input_size: int, calligraphy_style: str | None = None) -> np.ndarray | None:
    image = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    if image is None:
        return None
    resized = cv2.resize(image, (input_size, input_size), interpolation=cv2.INTER_AREA)
    normalized = resized.astype(np.float32) / 255.0
    flat = normalized.reshape(-1)
    char_code = np.asarray([encode_character(character)], dtype=np.float32)
    style_code = np.asarray([encode_calligraphy_style(calligraphy_style)], dtype=np.float32)
    extras = extract_quality_features(resized)
    return np.concatenate([flat, char_code, extras, style_code], axis=0)


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


def load_dataset(manifest_path: Path, input_size: int) -> tuple[np.ndarray, np.ndarray, list[dict]]:
    samples = load_manifest(manifest_path)
    features = []
    labels = []
    kept = []
    for sample in samples:
        path = Path(sample["path"])
        feature = build_features(
            path,
            sample.get("character", ""),
            input_size=input_size,
            calligraphy_style=sample.get("calligraphy_style") or sample.get("style"),
        )
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
) -> dict:
    X, y, kept_samples = load_dataset(manifest_path, input_size=input_size)

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

    output_dir.mkdir(parents=True, exist_ok=True)
    onnx_path = output_dir / "quality_scorer.onnx"
    sample_input = np.zeros((1, X.shape[1]), dtype=np.float32)
    onnx_model = to_onnx(
        model,
        initial_types=[("input", FloatTensorType([None, X.shape[1]]))],
        options={id(model): {"zipmap": False}},
        target_opset=17,
    )
    onnx_path.write_bytes(onnx_model.SerializeToString())

    metrics = {
        "manifest": str(manifest_path),
        "output_dir": str(output_dir),
        "input_size": input_size,
        "feature_dim": int(X.shape[1]),
        "sample_count": int(len(kept_samples)),
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
    (output_dir / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser(description="Train the InkPi quality scorer and export ONNX.")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--input-size", type=int, default=32)
    parser.add_argument("--hidden1", type=int, default=256)
    parser.add_argument("--hidden2", type=int, default=128)
    parser.add_argument("--max-iter", type=int, default=24)
    parser.add_argument("--test-size", type=float, default=0.18)
    args = parser.parse_args()

    metrics = train_model(
        manifest_path=args.manifest,
        output_dir=args.output_dir,
        input_size=args.input_size,
        hidden1=args.hidden1,
        hidden2=args.hidden2,
        max_iter=args.max_iter,
        test_size=args.test_size,
    )
    print(json.dumps(metrics, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
