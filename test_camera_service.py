"""Unit tests for camera framing controls."""

from __future__ import annotations

import unittest

import numpy as np

from services.camera_service import CameraService


class CameraServiceViewSettingsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.camera = CameraService()
        self.camera.reset_view_settings()

    def test_default_view_settings(self) -> None:
        settings = self.camera.get_view_settings()
        self.assertEqual(settings["lens_mode"], "wide")
        self.assertAlmostEqual(settings["zoom_ratio"], 1.0, places=2)
        self.assertGreaterEqual(settings["guide_scale"], 0.6)

    def test_zoom_transform_preserves_shape_and_crops_edges(self) -> None:
        frame = np.zeros((120, 160, 3), dtype=np.uint8)
        frame[:, :20] = (0, 0, 255)
        frame[:, -20:] = (0, 255, 0)
        frame[40:80, 60:100] = (255, 255, 255)

        self.camera.set_view_settings(lens_mode="detail", zoom_ratio=2.0)
        transformed = self.camera.apply_view_transform(frame)

        self.assertEqual(transformed.shape, frame.shape)
        self.assertLess(np.mean(transformed[:, :10, 2]), 200)
        self.assertLess(np.mean(transformed[:, -10:, 1]), 200)
        self.assertGreater(np.mean(transformed[45:75, 65:95]), 200)

    def test_nudge_and_reset_zoom(self) -> None:
        settings = self.camera.nudge_zoom(1)
        self.assertGreater(settings["zoom_ratio"], 1.0)

        reset = self.camera.reset_view_settings()
        self.assertEqual(reset["lens_mode"], "wide")
        self.assertAlmostEqual(reset["zoom_ratio"], 1.0, places=2)


if __name__ == "__main__":
    unittest.main()
