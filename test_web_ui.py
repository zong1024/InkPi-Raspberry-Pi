"""Smoke tests for the local InkPi WebUI."""

from __future__ import annotations

import unittest

from web_ui.app import app, state


class WebUiSmokeTest(unittest.TestCase):
    def setUp(self) -> None:
        self.client = app.test_client()
        with state.lock:
            state.selected_character = None
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
        self.assertIn("characters", payload)
        self.assertIn("history", payload)
        self.assertIn("selection", payload)
        response.close()

    def test_selection_roundtrip(self) -> None:
        response = self.client.post("/api/selection", json={"character": "shui"})
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["locked"])
        self.assertEqual(payload["key"], "shui")
        response.close()

        cleared = self.client.post("/api/selection", json={"character": None})
        self.assertEqual(cleared.status_code, 200)
        self.assertFalse(cleared.get_json()["locked"])
        cleared.close()


if __name__ == "__main__":
    unittest.main()
