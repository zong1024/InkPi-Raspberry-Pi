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


if __name__ == "__main__":
    unittest.main()
