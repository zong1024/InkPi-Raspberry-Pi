"""Style classification service with deterministic template fallback."""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Dict, Optional, Tuple

import cv2
import numpy as np

try:
    import onnxruntime as ort

    ONNX_AVAILABLE = True
except ImportError:
    ONNX_AVAILABLE = False

import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import DATA_DIR
from services.siamese_engine import siamese_engine
from services.template_manager import template_manager


STYLE_CLASSES = {
    0: "楷书",
    1: "行书",
    2: "草书",
    3: "隶书",
    4: "篆书",
}


class StyleClassificationService:
    """Classify calligraphy style with graceful fallback."""

    def __init__(self, model_path: str | None = None, use_quantized: bool = True) -> None:
        self.logger = logging.getLogger(__name__)
        self.model_dir = DATA_DIR / "models"
        self.model_dir.mkdir(parents=True, exist_ok=True)

        if model_path:
            self.model_path = Path(model_path)
        else:
            model_name = "style_classifier_int8.onnx" if use_quantized else "style_classifier.onnx"
            self.model_path = self.model_dir / model_name

        self.session = None
        self.input_name = None
        self.output_name = None
        self._init_onnx_session()

    def _init_onnx_session(self) -> None:
        if not ONNX_AVAILABLE or not self.model_path.exists():
            if not self.model_path.exists():
                self.logger.debug(
                    "Optional style classification model not found at %s; using template fallback.",
                    self.model_path,
                )
            return

        try:
            sess_options = ort.SessionOptions()
            sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
            sess_options.intra_op_num_threads = 4
            self.session = ort.InferenceSession(
                str(self.model_path),
                sess_options,
                providers=["CPUExecutionProvider"],
            )
            self.input_name = self.session.get_inputs()[0].name
            self.output_name = self.session.get_outputs()[0].name
            self.logger.info("Style ONNX model loaded: %s", self.model_path)
        except Exception as exc:  # noqa: BLE001
            self.logger.warning("Failed to initialize style ONNX session: %s", exc)
            self.session = None

    def classify(
        self,
        image: np.ndarray,
        character_hint: Optional[str] = None,
    ) -> Tuple[str, float, Dict[str, float]]:
        """Return style label, confidence and class probabilities."""
        start_time = time.time()
        fallback_style, fallback_conf, fallback_probs = self._template_fallback(image, character_hint)

        if self.session is None:
            self.logger.debug(
                "Style fallback selected %s (%.2f) in %.1f ms",
                fallback_style,
                fallback_conf,
                (time.time() - start_time) * 1000,
            )
            return fallback_style, fallback_conf, fallback_probs

        try:
            processed = self._preprocess(image)
            style, confidence, probs = self._inference_onnx(processed)
            if confidence >= max(0.45, fallback_conf):
                return style, confidence, probs
        except Exception as exc:  # noqa: BLE001
            self.logger.warning("Style ONNX inference failed, using fallback: %s", exc)

        return fallback_style, fallback_conf, fallback_probs

    def _preprocess(self, image: np.ndarray) -> np.ndarray:
        gray = image.copy() if len(image.shape) == 2 else cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        resized = cv2.resize(gray, (128, 128), interpolation=cv2.INTER_AREA)
        normalized = resized.astype(np.float32) / 255.0
        normalized = (normalized - 0.5) / 0.5
        return normalized.reshape(1, 1, 128, 128).astype(np.float32)

    def _inference_onnx(self, processed: np.ndarray) -> Tuple[str, float, Dict[str, float]]:
        outputs = self.session.run([self.output_name], {self.input_name: processed})
        logits = outputs[0][0]
        logits = logits - np.max(logits)
        probs = np.exp(logits)
        probs = probs / np.sum(probs)
        all_probs = {STYLE_CLASSES[i]: float(probs[i]) for i in range(min(len(STYLE_CLASSES), len(probs)))}
        best_idx = int(np.argmax(probs))
        return STYLE_CLASSES.get(best_idx, "楷书"), float(probs[best_idx]), all_probs

    def _template_fallback(
        self,
        image: np.ndarray,
        character_hint: Optional[str],
    ) -> Tuple[str, float, Dict[str, float]]:
        available_styles = template_manager.list_all_styles()
        if not available_styles:
            return "楷书", 0.0, {"楷书": 1.0}

        if len(available_styles) == 1:
            display = template_manager.to_display_style(available_styles[0])
            return display, 1.0, {display: 1.0}

        candidate_scores: Dict[str, float] = {}
        if character_hint:
            template_infos = template_manager.iter_character_templates(character_hint)
        else:
            template_infos = template_manager.iter_templates()

        if not template_infos:
            display = template_manager.to_display_style(available_styles[0])
            return display, 0.6, {template_manager.to_display_style(style): 0.0 for style in available_styles}

        for template_info in template_infos:
            template = cv2.imread(template_info["path"], cv2.IMREAD_GRAYSCALE)
            if template is None:
                continue
            structure_score, balance_score = siamese_engine.compare_structure(image, template)
            final_score = structure_score * 0.75 + balance_score * 0.25
            style_key = template_manager.resolve_style_key(template_info["style"])
            candidate_scores[style_key] = max(candidate_scores.get(style_key, 0.0), final_score)

        if not candidate_scores:
            display = template_manager.to_display_style(available_styles[0])
            return display, 0.6, {template_manager.to_display_style(style): 0.0 for style in available_styles}

        ordered = sorted(candidate_scores.items(), key=lambda item: item[1], reverse=True)
        best_style, best_score = ordered[0]
        second_score = ordered[1][1] if len(ordered) > 1 else 0.0
        confidence = max(0.0, min(1.0, ((best_score - 45.0) / 35.0) * 0.7 + ((best_score - second_score) / 15.0) * 0.3))

        probs = {
            template_manager.to_display_style(style): float(max(0.0, min(1.0, score / max(best_score, 1.0))))
            for style, score in ordered
        }
        return template_manager.to_display_style(best_style), float(confidence), probs

    def is_model_loaded(self) -> bool:
        return self.session is not None

    def get_model_info(self) -> Dict[str, str]:
        return {
            "model_path": str(self.model_path),
            "model_exists": str(self.model_path.exists()),
            "onnx_available": str(ONNX_AVAILABLE),
            "model_loaded": str(self.is_model_loaded()),
            "num_classes": str(len(STYLE_CLASSES)),
            "styles": ",".join(STYLE_CLASSES.values()),
        }


style_classification_service = StyleClassificationService()
