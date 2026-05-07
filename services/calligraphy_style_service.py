"""Runtime calligraphy style selection for InkPi."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from config import CALLIGRAPHY_STYLE_CONFIG, PATHS


class CalligraphyStyleService:
    """Restrict runtime recognition/scoring to Kaishu and Xingshu modes."""

    def __init__(self) -> None:
        self.logger = logging.getLogger(__name__)
        self.allowed: dict[str, str] = dict(CALLIGRAPHY_STYLE_CONFIG["allowed"])
        self.settings_path = Path(PATHS["cache_dir"]) / "runtime_settings.json"
        self._style = self.normalize(CALLIGRAPHY_STYLE_CONFIG.get("default", "kaishu"))
        self._load()

    def normalize(self, value: str | None) -> str:
        raw = str(value or "").strip().lower()
        aliases = {
            "kai": "kaishu",
            "regular": "kaishu",
            "楷": "kaishu",
            "楷书": "kaishu",
            "xing": "xingshu",
            "running": "xingshu",
            "行": "xingshu",
            "行书": "xingshu",
        }
        normalized = aliases.get(raw, raw)
        return normalized if normalized in self.allowed else "kaishu"

    @property
    def current_style(self) -> str:
        return self._style

    @property
    def current_label(self) -> str:
        return self.label_for(self._style)

    def label_for(self, style: str | None) -> str:
        return self.allowed.get(self.normalize(style), self.allowed["kaishu"])

    def style_code(self, style: str | None = None) -> float:
        return 1.0 if self.normalize(style or self._style) == "xingshu" else 0.0

    def set_style(self, style: str) -> str:
        self._style = self.normalize(style)
        self._save()
        self.logger.info("Calligraphy style set to %s", self._style)
        return self._style

    def _load(self) -> None:
        if not self.settings_path.exists():
            return
        try:
            payload = json.loads(self.settings_path.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            self.logger.debug("Skip loading runtime settings: %s", exc)
            return
        self._style = self.normalize(payload.get("calligraphy_style"))

    def _save(self) -> None:
        self.settings_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"calligraphy_style": self._style}
        self.settings_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


calligraphy_style_service = CalligraphyStyleService()
