"""Smoke tests for the local InkPi WebUI."""

from __future__ import annotations

import unittest

from web_ui.app import app, state


class WebUiSmokeTest(unittest.TestCase):
    def setUp(self) -> None:
        self.client = app.test_client()
        with state.lock:
            state.last_result = None
            state.last_result_id = None

    def test_health(self) -> None:
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["status"], "ok")
        response.close()

    def test_index(self) -> None:
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"InkPi", response.data)
        response.close()

    def test_bootstrap(self) -> None:
        response = self.client.get("/api/bootstrap")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertIn("history", payload)
        self.assertIn("camera_settings", payload)
        self.assertIn("stats", payload)
        self.assertNotIn("selection", payload)
        self.assertNotIn("characters", payload)
        response.close()

    def test_history_endpoint(self) -> None:
        response = self.client.get("/api/history")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertIn("items", payload)
        self.assertIsInstance(payload["items"], list)
        response.close()

    def test_camera_settings_roundtrip(self) -> None:
        response = self.client.get("/api/camera/settings")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertIn("lens_mode", payload)
        self.assertIn("zoom_ratio", payload)
        response.close()

        updated = self.client.post("/api/camera/settings", json={"lens_mode": "detail", "zoom_ratio": 1.6})
        self.assertEqual(updated.status_code, 200)
        updated_payload = updated.get_json()
        self.assertEqual(updated_payload["lens_mode"], "detail")
        self.assertAlmostEqual(updated_payload["zoom_ratio"], 1.6, places=1)
        updated.close()

        reset = self.client.post("/api/camera/settings", json={"reset": True})
        self.assertEqual(reset.status_code, 200)
        reset_payload = reset.get_json()
        self.assertEqual(reset_payload["lens_mode"], "wide")
        self.assertAlmostEqual(reset_payload["zoom_ratio"], 1.0, places=1)
        reset.close()

if __name__ == "__main__":
    unittest.main()
