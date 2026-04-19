"""Checks for rubric-aware training manifest preparation."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np

from training.build_quality_manifest import build_manifest
from training.train_quality_scorer import load_dataset


class TrainingManifestTests(unittest.TestCase):
    def test_manifest_exports_rubric_fields_and_training_can_read_it(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "regular"
            originals = root / "originals"
            good = root / "good"
            originals.mkdir(parents=True)
            good.mkdir(parents=True)

            image = np.full((64, 64), 255, dtype=np.uint8)
            cv2.putText(image, "Y", (12, 48), cv2.FONT_HERSHEY_SIMPLEX, 1.4, 0, 3, cv2.LINE_AA)
            cv2.imwrite(str(originals / "sample_0.png"), image)
            cv2.imwrite(str(good / "sample_good_1.png"), image)

            manifest_path = Path(temp_dir) / "quality_manifest.jsonl"
            summary = build_manifest(
                public_character_dir=root,
                output_path=manifest_path,
                limit_good=4,
                limit_medium=4,
                limit_bad=4,
                script="regular",
            )

            self.assertEqual(summary["rubric_version"], "source_backed_rubric_v1")
            self.assertEqual(summary["rubric_family"], "regular_rubric_v1")

            first_record = json.loads(manifest_path.read_text(encoding="utf-8").splitlines()[0])
            self.assertEqual(first_record["rubric_version"], "source_backed_rubric_v1")
            self.assertEqual(first_record["rubric_family"], "regular_rubric_v1")
            self.assertTrue(first_record["rubric_items"])
            self.assertIn("rubric_preview_total", first_record)

            features, labels, kept_samples = load_dataset(manifest_path, input_size=32, script="regular")
            self.assertGreater(features.shape[0], 0)
            self.assertEqual(features.shape[0], labels.shape[0])
            self.assertTrue(all(sample["rubric_items"] for sample in kept_samples))


if __name__ == "__main__":
    unittest.main()
