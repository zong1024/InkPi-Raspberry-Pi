"""Tests for the remote OCR candidate provider."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
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

        payload = {
            "ok": True,
            "items": [
                {"key": "shen", "display": "神", "score": 0.91, "provider": "remote_ocr"},
                {"key": "shui", "display": "水", "score": 0.72, "provider": "remote_ocr"},
            ],
        }
        fake_response = Mock()
        fake_response.content = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        fake_response.raise_for_status.return_value = None

        image = np.ones((128, 128), dtype=np.uint8) * 255
        with patch("full_recognition_v2.http_provider.requests.post", return_value=fake_response) as post:
            candidates = provider.get_candidates(image, limit=4)

        self.assertEqual(len(candidates), 2)
        self.assertEqual(candidates[0].display, "神")
        self.assertEqual(candidates[0].key, "shen")
        self.assertGreater(candidates[0].provider_score, candidates[1].provider_score)
        post.assert_called_once()

    def test_provider_bootstraps_cloud_env_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_root = Path(tmp_dir)
            env_dir = project_root / ".inkpi"
            env_dir.mkdir(parents=True, exist_ok=True)
            (env_dir / "cloud.env").write_text(
                "INKPI_CLOUD_BACKEND_URL=http://env.example:5001\n"
                "INKPI_CLOUD_DEVICE_KEY=env-device-key\n",
                encoding="utf-8",
            )

            with (
                patch.dict(
                    os.environ,
                    {
                        "INKPI_CLOUD_BACKEND_URL": "",
                        "INKPI_CLOUD_DEVICE_KEY": "",
                    },
                    clear=False,
                ),
                patch(
                    "full_recognition_v2.http_provider.Path.resolve",
                    return_value=project_root / "full_recognition_v2" / "http_provider.py",
                ),
            ):
                provider = HttpOcrCandidateProvider()

            self.assertEqual(
                provider.endpoint,
                "http://env.example:5001/api/device/full-recognition/candidates",
            )
            self.assertEqual(provider.device_key, "env-device-key")


if __name__ == "__main__":
    unittest.main()
