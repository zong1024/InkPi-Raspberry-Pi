"""Character recognition service with deterministic template fallback."""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Dict, List, Tuple

import cv2
import numpy as np

try:
    import onnxruntime as ort

    ONNX_AVAILABLE = True
except ImportError:
    ONNX_AVAILABLE = False

import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import DATA_DIR, MODEL_CONFIG
from models.recognition_result import RecognitionResult
from services.preprocessing_service import preprocessing_service
from services.siamese_engine import siamese_engine
from services.template_manager import template_manager


class RecognitionService:
    """Recognize a single character from the processed binary image."""

    def __init__(
        self,
        model_path: str | None = None,
        use_quantized: bool = True,
        num_classes: int = 1000,
        input_size: Tuple[int, int] = (64, 64),
    ) -> None:
        self.logger = logging.getLogger(__name__)
        self.input_size = input_size
        self.num_classes = num_classes
        self.use_quantized = use_quantized
        inference_cfg = MODEL_CONFIG.get("inference", {})
        self.num_threads = int(inference_cfg.get("num_threads", 4))

        self.model_dir = DATA_DIR / "models"
        self.model_dir.mkdir(parents=True, exist_ok=True)

        if model_path:
            self.model_path = Path(model_path)
        else:
            model_name = "ch_recognize_mobile_int8.onnx" if use_quantized else "ch_recognize_mobile.onnx"
            self.model_path = self.model_dir / model_name

        self.session = None
        self.input_name = None
        self.output_name = None

        if ONNX_AVAILABLE:
            self._init_onnx_session()
        else:
            self.logger.info("ONNX Runtime unavailable; using deterministic template fallback.")
        self.min_template_score = 57.0
        self.min_character_confidence = 0.46
        self.min_candidate_gap = 4.0
        self.min_top2_gap = 0.8
        self.min_top3_gap = 1.2
        self.strong_match_score = 88.0

    def _init_onnx_session(self) -> None:
        """Initialize the ONNX runtime session if the optional model exists."""
        if not self.model_path.exists():
            self.logger.debug(
                "Optional recognition model not found at %s; using template fallback.",
                self.model_path,
            )
            return

        try:
            sess_options = ort.SessionOptions()
            sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
            sess_options.intra_op_num_threads = self.num_threads
            sess_options.inter_op_num_threads = 1
            self.session = ort.InferenceSession(
                str(self.model_path),
                sess_options,
                providers=["CPUExecutionProvider"],
            )
            self.input_name = self.session.get_inputs()[0].name
            self.output_name = self.session.get_outputs()[0].name
            input_shape = self.session.get_inputs()[0].shape
            if len(input_shape) == 4 and input_shape[2] and input_shape[3]:
                self.input_size = (int(input_shape[2]), int(input_shape[3]))
            self.logger.info("Recognition ONNX model loaded: %s", self.model_path)
        except Exception as exc:  # noqa: BLE001
            self.logger.warning("Failed to initialize recognition ONNX session: %s", exc)
            self.session = None

    def recognize(self, image: np.ndarray, top_k: int = 5) -> RecognitionResult:
        """Recognize the character in the given image."""
        start_time = time.time()

        fallback_result = self._template_fallback(image, top_k=max(top_k, 2))
        result = fallback_result

        if self.session is not None:
            try:
                processed = self._preprocess(image)
                onnx_result = self._inference_onnx(processed, top_k=max(top_k, 2))
                result = self._choose_better_result(onnx_result, fallback_result)
            except Exception as exc:  # noqa: BLE001
                self.logger.warning("Recognition ONNX inference failed, fallback to templates: %s", exc)

        result.inference_time_ms = (time.time() - start_time) * 1000
        return result

    def _preprocess(self, image: np.ndarray) -> np.ndarray:
        """Prepare image tensor for the optional ONNX classifier."""
        gray = self._to_grayscale(image)
        h, w = self.input_size
        resized = cv2.resize(gray, (w, h), interpolation=cv2.INTER_AREA)
        normalized = resized.astype(np.float32) / 255.0
        normalized = (normalized - 0.5) / 0.5
        return normalized.reshape(1, 1, h, w).astype(np.float32)

    def _inference_onnx(self, processed: np.ndarray, top_k: int) -> RecognitionResult:
        """Run the optional ONNX classifier."""
        outputs = self.session.run([self.output_name], {self.input_name: processed})
        logits = outputs[0][0]
        logits = logits - np.max(logits)
        probs = np.exp(logits)
        probs = probs / np.sum(probs)
        top_indices = np.argsort(probs)[::-1][:top_k]
        candidates = [(str(index), float(probs[index])) for index in top_indices]
        best_label, best_confidence = candidates[0]
        return RecognitionResult(
            character=best_label,
            confidence=float(best_confidence),
            candidates=candidates,
            source="onnx",
        )

    def _template_fallback(self, image: np.ndarray, top_k: int) -> RecognitionResult:
        """Use the Siamese model plus geometric heuristics to match templates."""
        binary = self._prepare_binary(image)
        if not self._looks_like_single_character(binary):
            return RecognitionResult(
                character="",
                confidence=0.0,
                candidates=[],
                source="template_rejected",
            )

        raw_candidates: List[Tuple[str, float, str]] = []
        for template_info in template_manager.iter_templates():
            template = cv2.imread(template_info["path"], cv2.IMREAD_GRAYSCALE)
            if template is None:
                continue

            structure_score, balance_score = siamese_engine.compare_structure(binary, template)
            projection_score = self._projection_similarity(binary, template) * 100.0
            contour_score = self._contour_similarity(binary, template) * 100.0

            final_score = (
                structure_score * 0.60
                + balance_score * 0.10
                + projection_score * 0.20
                + contour_score * 0.10
            )
            raw_candidates.append((template_info["char"], float(final_score), template_info["style"]))

        if not raw_candidates:
            return RecognitionResult(
                character="",
                confidence=0.0,
                candidates=[],
                source="template_missing",
            )

        best_by_character: Dict[str, Tuple[float, str]] = {}
        for character, score, style in raw_candidates:
            if character not in best_by_character or score > best_by_character[character][0]:
                best_by_character[character] = (score, style)

        ordered = sorted(best_by_character.items(), key=lambda item: item[1][0], reverse=True)
        top = ordered[:top_k]
        top_candidates = [
            (template_manager.to_display_character(char_key), self._score_to_confidence(score, ordered))
            for char_key, (score, _) in top
        ]

        best_key, (best_score, best_style) = ordered[0]
        confidence = self._score_to_confidence(best_score, ordered)
        gap = best_score - (ordered[1][1][0] if len(ordered) > 1 else 0.0)
        third_gap = best_score - (ordered[2][1][0] if len(ordered) > 2 else 0.0)

        if (
            (gap < self.min_top2_gap or third_gap < self.min_top3_gap)
            and best_score < self.strong_match_score
        ):
            return RecognitionResult(
                character="",
                confidence=float(confidence),
                candidates=top_candidates,
                source="template_ambiguous",
            )

        if best_score < self.min_template_score or (gap < self.min_candidate_gap and confidence < self.min_character_confidence):
            return RecognitionResult(
                character="",
                confidence=float(confidence),
                candidates=top_candidates,
                source="template_low_confidence",
            )

        return RecognitionResult(
            character=template_manager.to_display_character(best_key),
            confidence=float(confidence),
            candidates=top_candidates,
            source=f"template:{template_manager.to_display_style(best_style)}",
        )

    def _choose_better_result(self, primary: RecognitionResult, fallback: RecognitionResult) -> RecognitionResult:
        """Choose the stronger result between ONNX and template fallback."""
        if not fallback.character:
            return primary
        if not primary.character:
            return fallback
        if primary.character.isdigit():
            return fallback
        return fallback if fallback.confidence >= primary.confidence else primary

    def _to_grayscale(self, image: np.ndarray) -> np.ndarray:
        if len(image.shape) == 3:
            return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        return image.copy()

    def _prepare_binary(self, image: np.ndarray) -> np.ndarray:
        gray = self._to_grayscale(image)
        unique_values = np.unique(gray)
        if len(unique_values) <= 2 and set(unique_values.tolist()).issubset({0, 255}):
            cleaned = preprocessing_service._extract_primary_subject(gray)
            resized = cv2.resize(cleaned, (224, 224), interpolation=cv2.INTER_NEAREST)
        else:
            cleaned = preprocessing_service._build_precheck_binary(gray)
            resized = cv2.resize(cleaned, (224, 224), interpolation=cv2.INTER_AREA)
        _, binary = cv2.threshold(resized, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        if np.mean(binary == 0) > 0.5:
            binary = 255 - binary
        binary = preprocessing_service._extract_primary_subject(binary)
        return binary

    def _looks_like_single_character(self, binary: np.ndarray) -> bool:
        ink_ratio = float(np.mean(binary == 0))
        if ink_ratio < 0.01 or ink_ratio > 0.45:
            return False

        components = self._meaningful_components(binary)
        if components == 0:
            return False

        contours, _ = cv2.findContours(255 - binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return False

        largest = max(contours, key=cv2.contourArea)
        area = float(cv2.contourArea(largest))
        x, y, w, h = cv2.boundingRect(largest)
        bbox_fill = area / max(1, w * h)
        edges = cv2.Canny(binary, 40, 120)
        edge_to_ink = float(np.sum(edges > 0)) / max(1, np.sum(binary == 0))
        if bbox_fill > 0.95 and edge_to_ink < 0.08:
            return False
        if components > 120 and edge_to_ink < 0.12:
            return False
        return edge_to_ink >= 0.05

    def _meaningful_components(self, binary: np.ndarray) -> int:
        num_labels, _, stats, _ = cv2.connectedComponentsWithStats(255 - binary, connectivity=8)
        if num_labels <= 1:
            return 0
        min_area = max(10, int(binary.size * 0.0001))
        areas = stats[1:, cv2.CC_STAT_AREA]
        return int(np.sum(areas >= min_area))

    def _projection_similarity(self, image_a: np.ndarray, image_b: np.ndarray) -> float:
        binary_a = self._prepare_binary(image_a)
        binary_b = self._prepare_binary(image_b)
        proj_a_x = np.mean(binary_a == 0, axis=0)
        proj_a_y = np.mean(binary_a == 0, axis=1)
        proj_b_x = np.mean(binary_b == 0, axis=0)
        proj_b_y = np.mean(binary_b == 0, axis=1)
        diff = (np.mean(np.abs(proj_a_x - proj_b_x)) + np.mean(np.abs(proj_a_y - proj_b_y))) / 2.0
        return float(max(0.0, 1.0 - diff))

    def _contour_similarity(self, image_a: np.ndarray, image_b: np.ndarray) -> float:
        binary_a = self._prepare_binary(image_a)
        binary_b = self._prepare_binary(image_b)
        contours_a, _ = cv2.findContours(255 - binary_a, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        contours_b, _ = cv2.findContours(255 - binary_b, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours_a or not contours_b:
            return 0.0
        contour_a = max(contours_a, key=cv2.contourArea)
        contour_b = max(contours_b, key=cv2.contourArea)
        distance = cv2.matchShapes(contour_a, contour_b, cv2.CONTOURS_MATCH_I1, 0.0)
        return float(1.0 / (1.0 + max(distance, 0.0) * 8.0))

    def _score_to_confidence(self, best_score: float, ordered_candidates: List[Tuple[str, Tuple[float, str]]]) -> float:
        second_score = ordered_candidates[1][1][0] if len(ordered_candidates) > 1 else 0.0
        score_term = max(0.0, min(1.0, (best_score - 45.0) / 35.0))
        gap_term = max(0.0, min(1.0, (best_score - second_score) / 18.0))
        confidence = score_term * 0.75 + gap_term * 0.25
        return float(max(0.0, min(1.0, confidence)))

    def recognize_batch(self, images: List[np.ndarray], top_k: int = 5) -> List[RecognitionResult]:
        """Recognize a batch of images."""
        return [self.recognize(image, top_k=top_k) for image in images]

    def download_model(self, model_type: str = "mobile") -> None:
        """Document how to install an optional recognition model."""
        self.logger.info("Recognition model download is manual. Place the model under %s", self.model_dir)
        self.logger.info("Suggested sources: PaddleOCR or another small Chinese OCR model (%s)", model_type)

    def is_model_loaded(self) -> bool:
        """Whether the optional ONNX recognition model is available."""
        return self.session is not None

    def get_model_info(self) -> Dict[str, str]:
        """Return model metadata for diagnostics."""
        return {
            "model_path": str(self.model_path),
            "model_exists": str(self.model_path.exists()),
            "onnx_available": str(ONNX_AVAILABLE),
            "model_loaded": str(self.is_model_loaded()),
            "input_size": str(self.input_size),
            "num_classes": str(self.num_classes),
            "use_quantized": str(self.use_quantized),
        }


recognition_service = RecognitionService()
