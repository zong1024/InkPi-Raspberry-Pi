"""Desktop simulator smoke tests."""

from __future__ import annotations

import os
import unittest

os.environ.setdefault("INKPI_DESKTOP_SIM", "1")

from services.camera_service import camera_service
from services.evaluation_service import evaluation_service
from services.local_ocr_service import local_ocr_service
from services.quality_scorer_service import quality_scorer_service


class DesktopSimulatorTests(unittest.TestCase):
    def test_sim_camera_and_evaluation_pipeline(self) -> None:
        self.assertTrue(camera_service.open())
        frame = camera_service.capture_frame()
        camera_service.close()

        self.assertIsNotNone(frame)
        self.assertTrue(local_ocr_service.available)
        self.assertTrue(quality_scorer_service.available)

        result = evaluation_service.evaluate(frame)
        self.assertIsNotNone(result.character_name)
        self.assertTrue(0 <= result.total_score <= 100)
        self.assertIn(result.quality_level, {"bad", "medium", "good"})
        self.assertIsNotNone(result.dimension_scores)


if __name__ == "__main__":
    unittest.main()
