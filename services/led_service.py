"""LED controller service for the Raspberry Pi runtime."""

from __future__ import annotations

import logging
from pathlib import Path
import threading
import time
from typing import Optional


def _detect_raspberry_pi() -> bool:
    model_path = Path("/proc/device-tree/model")
    try:
        return model_path.exists() and "Raspberry Pi" in model_path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return False


IS_RASPBERRY_PI = _detect_raspberry_pi()

try:
    if IS_RASPBERRY_PI:
        import spidev  # type: ignore
    else:
        spidev = None  # type: ignore[assignment]
except Exception:  # noqa: BLE001
    spidev = None  # type: ignore[assignment]

LED_AVAILABLE = bool(IS_RASPBERRY_PI and spidev is not None)


class LEDService:
    """Control the LED strip when hardware is present, otherwise simulate it."""

    COLORS = {
        "green": (0, 255, 100),
        "cyan": (0, 255, 255),
        "yellow": (255, 200, 0),
        "orange": (255, 100, 0),
        "red": (255, 0, 0),
        "white": (255, 255, 255),
        "off": (0, 0, 0),
    }

    def __init__(self, num_leds: int = 8, spi_bus: int = 0, spi_device: int = 0) -> None:
        self.logger = logging.getLogger(__name__)
        self.num_leds = num_leds
        self.spi_bus = spi_bus
        self.spi_device = spi_device
        self.brightness = 0.3
        self.available = LED_AVAILABLE
        self._disabled_reason: str | None = None
        self._animation_thread: threading.Thread | None = None
        self._stop_animation = threading.Event()
        self.spi = None

        if self.available:
            self._init_spi()
        else:
            self._disabled_reason = "LED hardware is unavailable on this device."
            self.logger.info("%s Running in simulation mode.", self._disabled_reason)

    def _init_spi(self) -> None:
        device_path = Path(f"/dev/spidev{self.spi_bus}.{self.spi_device}")
        if not device_path.exists():
            self.available = False
            self._disabled_reason = f"SPI device {device_path} is not available."
            self.logger.debug("%s Falling back to simulation mode.", self._disabled_reason)
            return

        try:
            self.spi = spidev.SpiDev()
            self.spi.open(self.spi_bus, self.spi_device)
            self.spi.max_speed_hz = 2_000_000
            self.spi.mode = 0
        except Exception as exc:  # noqa: BLE001
            self.available = False
            self._disabled_reason = f"SPI initialization failed: {exc}"
            self.logger.debug("%s Falling back to simulation mode.", self._disabled_reason)
            self.spi = None

    def _apply_brightness(self, r: int, g: int, b: int) -> tuple[int, int, int]:
        return (int(r * self.brightness), int(g * self.brightness), int(b * self.brightness))

    def _encode_color(self, r: int, g: int, b: int) -> bytes:
        data = []
        for byte in (g, r, b):
            for bit in range(7, -1, -1):
                data.append(0xE0 if byte & (1 << bit) else 0xC0)
        return bytes(data)

    def _write_frame(self, rgb: tuple[int, int, int], led_index: Optional[int] = None) -> None:
        if not self.available or self.spi is None:
            self.logger.debug("[LED simulation] rgb=%s led=%s", rgb, led_index)
            return

        frame = bytearray([0x00] * 4)
        for index in range(self.num_leds):
            frame.extend(self._encode_color(*(rgb if led_index is None or index == led_index else (0, 0, 0))))
        frame.extend([0x00] * 4)

        try:
            self.spi.writebytes(list(frame))
        except Exception as exc:  # noqa: BLE001
            self.available = False
            self._disabled_reason = f"LED write failed: {exc}"
            self.logger.debug("%s Falling back to simulation mode.", self._disabled_reason)

    def set_color(self, color_name: str, led_index: Optional[int] = None) -> None:
        rgb = self.COLORS.get(color_name, self.COLORS["off"])
        self.set_rgb(*rgb, led_index=led_index)

    def set_rgb(self, r: int, g: int, b: int, led_index: Optional[int] = None) -> None:
        self._write_frame(self._apply_brightness(r, g, b), led_index=led_index)

    def off(self) -> None:
        self.set_color("off")

    def stop_animation(self) -> None:
        self._stop_animation.set()
        if self._animation_thread and self._animation_thread.is_alive():
            self._animation_thread.join(timeout=1.0)
        self._animation_thread = None
        self._stop_animation.clear()

    def _start_animation(self, worker) -> None:
        self.stop_animation()
        self._animation_thread = threading.Thread(target=worker, daemon=True)
        self._animation_thread.start()

    def show_score(self, score: int) -> None:
        if score >= 85:
            self._start_animation(self._breathing_worker("green", "cyan", 1.8))
        elif score >= 70:
            self.stop_animation()
            self.set_color("yellow")
        else:
            self._start_animation(self._blinking_worker("red", 0.3))

    def show_success(self) -> None:
        self.stop_animation()
        self.set_color("green")
        time.sleep(0.4)
        self.off()

    def show_error(self) -> None:
        self.stop_animation()
        for _ in range(3):
            self.set_color("red")
            time.sleep(0.18)
            self.off()
            time.sleep(0.18)

    def show_loading(self) -> None:
        def worker() -> None:
            index = 0
            while not self._stop_animation.is_set():
                for led in range(self.num_leds):
                    self.set_rgb(0, 0, 0, led)
                self.set_rgb(120, 120, 120, index)
                index = (index + 1) % self.num_leds
                time.sleep(0.08)

        self._start_animation(worker)

    def _breathing_worker(self, color_a: str, color_b: str, duration: float):
        rgb_a = self.COLORS[color_a]
        rgb_b = self.COLORS[color_b]

        def worker() -> None:
            while not self._stop_animation.is_set():
                for step in range(0, 101, 5):
                    if self._stop_animation.is_set():
                        return
                    factor = step / 100.0
                    rgb = (
                        int(rgb_a[0] * factor + rgb_b[0] * (1 - factor)),
                        int(rgb_a[1] * factor + rgb_b[1] * (1 - factor)),
                        int(rgb_a[2] * factor + rgb_b[2] * (1 - factor)),
                    )
                    self.set_rgb(*rgb)
                    time.sleep(duration / 40.0)
                for step in range(100, -1, -5):
                    if self._stop_animation.is_set():
                        return
                    factor = step / 100.0
                    rgb = (
                        int(rgb_a[0] * factor + rgb_b[0] * (1 - factor)),
                        int(rgb_a[1] * factor + rgb_b[1] * (1 - factor)),
                        int(rgb_a[2] * factor + rgb_b[2] * (1 - factor)),
                    )
                    self.set_rgb(*rgb)
                    time.sleep(duration / 40.0)

        return worker

    def _blinking_worker(self, color: str, interval: float):
        def worker() -> None:
            while not self._stop_animation.is_set():
                self.set_color(color)
                time.sleep(interval)
                self.off()
                time.sleep(interval)

        return worker

    def release(self) -> None:
        self.stop_animation()
        self.off()
        if self.spi is not None:
            try:
                self.spi.close()
            except Exception:  # noqa: BLE001
                pass
            self.spi = None

    @property
    def disabled_reason(self) -> str | None:
        """Explain why the LED controller is unavailable."""
        return self._disabled_reason


led_service = LEDService()
