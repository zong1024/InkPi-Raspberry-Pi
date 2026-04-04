"""Cross-platform speech output service for InkPi."""

from __future__ import annotations

import logging
import os
import re
import threading
from pathlib import Path
from typing import Optional

import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import TTS_CONFIG


class SpeechService:
    """Thin TTS wrapper with graceful fallback when audio is unavailable."""

    def __init__(self) -> None:
        self.logger = logging.getLogger(__name__)
        self.config = TTS_CONFIG
        self._engine = None
        self._lock = threading.Lock()
        self._is_speaking = False
        self._audio_available: Optional[bool] = None
        self._tts_disabled_reason: Optional[str] = None
        self._tts_skip_logged = False

    def _check_audio_output(self) -> bool:
        """Detect whether local audio playback is available."""
        if self._audio_available is not None:
            return self._audio_available

        if os.environ.get("INKPI_FORCE_TTS") == "1":
            self._audio_available = True
            return True

        if not sys.platform.startswith("linux"):
            self._audio_available = True
            return True

        cards_path = Path("/proc/asound/cards")
        if cards_path.exists():
            try:
                cards_text = cards_path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                cards_text = ""

            has_card = any(re.match(r"^\s*\d+\s+\[", line) for line in cards_text.splitlines())
            if has_card:
                self._audio_available = True
                return True

        self._tts_disabled_reason = "No ALSA playback device detected"
        self._audio_available = False
        self.logger.debug("%s; speech playback disabled.", self._tts_disabled_reason)
        return False

    def _init_engine(self) -> None:
        """Initialize the TTS engine once."""
        if self._engine is not None:
            return

        if not self._check_audio_output():
            return

        try:
            import pyttsx3

            self._engine = pyttsx3.init()
            self._engine.setProperty("rate", self.config["rate"])
            self._engine.setProperty("volume", self.config["volume"])
            self._set_chinese_voice()
            self.logger.info("TTS engine initialized.")
        except Exception as exc:  # noqa: BLE001
            self.logger.error("Failed to initialize TTS engine: %s", exc)
            self._engine = None

    def _set_chinese_voice(self) -> None:
        """Prefer a Chinese-capable voice when one is available."""
        if self._engine is None:
            return

        voices = self._engine.getProperty("voices")
        keywords = ("chinese", "中文", "zh", "huihui", "kangkang", "yaoyao")

        for voice in voices:
            voice_name = str(getattr(voice, "name", "")).lower()
            voice_id = str(getattr(voice, "id", "")).lower()
            if any(keyword in voice_name or keyword in voice_id for keyword in keywords):
                self._engine.setProperty("voice", voice.id)
                self.logger.info("Selected TTS voice: %s", voice.name)
                return

        self.logger.warning("No Chinese TTS voice found; using default voice.")

    def speak(self, text: str, blocking: bool = False) -> bool:
        """Speak a text message."""
        if not text:
            return False

        self._init_engine()

        if self._engine is None:
            if self._tts_disabled_reason and not self._tts_skip_logged:
                self.logger.debug("Skipping speech playback: %s.", self._tts_disabled_reason)
                self._tts_skip_logged = True
            return False

        with self._lock:
            if self._is_speaking:
                self.logger.warning("Speech output is already active; skipping this request.")
                return False
            self._is_speaking = True

        def _speak_thread() -> None:
            try:
                self.logger.info("Speaking feedback: %s", text[:80])
                self._engine.say(text)
                self._engine.runAndWait()
            except Exception as exc:  # noqa: BLE001
                self.logger.error("Speech playback failed: %s", exc)
            finally:
                with self._lock:
                    self._is_speaking = False

        if blocking:
            _speak_thread()
        else:
            thread = threading.Thread(target=_speak_thread, daemon=True)
            thread.start()

        return True

    def speak_score(self, total_score: int, feedback: str | None = None) -> bool:
        """Speak the current evaluation summary."""
        if total_score >= 85:
            level = "优秀"
        elif total_score >= 70:
            level = "良好"
        else:
            level = "待提升"

        text = f"评测完成，得到 {total_score} 分，当前评价为 {level}。"
        if feedback:
            text += feedback
        return self.speak(text)

    def speak_error(self, error_message: str) -> bool:
        """Speak an error message when possible."""
        return self.speak(error_message)

    def stop(self) -> None:
        """Stop current playback if the engine is active."""
        if self._engine is not None:
            try:
                self._engine.stop()
            except Exception:  # noqa: BLE001
                pass

        with self._lock:
            self._is_speaking = False

    def is_speaking(self) -> bool:
        """Return whether speech playback is active."""
        with self._lock:
            return self._is_speaking

    @property
    def audio_available(self) -> bool:
        """Return whether local audio playback is currently available."""
        return self._check_audio_output()

    @property
    def disabled_reason(self) -> str | None:
        """Explain why speech playback is unavailable."""
        self._check_audio_output()
        return self._tts_disabled_reason


speech_service = SpeechService()
