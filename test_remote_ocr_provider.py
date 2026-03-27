"""Tests for the remote OCR candidate provider."""

from __future__ import annotations

import unittest
from unittest.mock import Mock, patch

import numpy as np

from full_recognition_v2.http_provider import HttpOcrCandidateProvider


class RemoteOcrProviderTest(unittest.TestCase):
    def test_remote_candidates_are_mapped(self) -> None:
        provider = HttpOcrCandidateProvider(
            endpoint="http://example.test/api/device/full-recognition/candidates",
            device_key="device-key",
            timeout=1.0,
        )

        fake_response = Mock()
        fake_response.json.return_value = {
            "ok": True,
            "items": [
                {"key": "神", "display": "神", "score": 0.91, "provider": "remote_ocr"},
                {"key": "水", "display": "水", "score": 0.72, "provider": "remote_ocr"},
            ],
        }
        fake_response.raise_for_status.return_value = None

        image = np.ones((128, 128), dtype=np.uint8) * 255
        with patch("full_recognition_v2.http_provider.requests.post", return_value=fake_response) as post:
            candidates = provider.get_candidates(image, limit=4)

        self.assertEqual(len(candidates), 2)
        self.assertEqual(candidates[0].display, "神")
        self.assertEqual(candidates[0].key, "shen")
        self.assertGreater(candidates[0].provider_score, candidates[1].provider_score)
        post.assert_called_once()


if __name__ == "__main__":
    unittest.main()
