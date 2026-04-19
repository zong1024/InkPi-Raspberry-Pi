"""Runtime monitoring and operations snapshots for the InkPi console."""

from __future__ import annotations

from collections import deque
from datetime import datetime
import itertools
import logging
import os
from pathlib import Path
import platform
import shutil
import socket
import threading
import time
from typing import Any

import requests

from config import APP_CONFIG, DATA_DIR, DB_PATH, IS_RASPBERRY_PI, LOG_CONFIG, PATHS


class _OperationsLogHandler(logging.Handler):
    """Capture runtime log lines into the operations buffer."""

    def __init__(self, monitor: "OperationsMonitorService") -> None:
        super().__init__(level=logging.INFO)
        self.monitor = monitor

    def emit(self, record: logging.LogRecord) -> None:
        try:
            message = self.format(record)
        except Exception:  # noqa: BLE001
            message = record.getMessage()
        self.monitor.append_log(level=record.levelname, source=record.name, message=message)


class OperationsMonitorService:
    """Keep lightweight runtime telemetry for the web operations console."""

    def __init__(self) -> None:
        self.logger = logging.getLogger(__name__)
        self.started_at = time.time()
        self.runtime_logs_dir = DATA_DIR / "runtime_logs"
        self.runtime_pids_dir = DATA_DIR / "runtime_pids"
        self._lock = threading.RLock()
        self._log_entries: deque[dict[str, Any]] = deque(maxlen=500)
        self._pipeline_events: deque[dict[str, Any]] = deque(maxlen=240)
        self._component_notes: dict[str, dict[str, Any]] = {}
        self._last_result: dict[str, Any] | None = None
        self._log_counter = itertools.count(1)
        self._event_counter = itertools.count(1)
        self._http_cache: dict[str, tuple[float, dict[str, Any]]] = {}
        self._log_handler: _OperationsLogHandler | None = None

    def attach_logging(self) -> None:
        """Install a root logger handler exactly once."""
        with self._lock:
            if self._log_handler is not None:
                return

            handler = _OperationsLogHandler(self)
            handler.setFormatter(
                logging.Formatter(
                    LOG_CONFIG.get("format", "%(asctime)s - %(name)s - %(levelname)s - %(message)s")
                )
            )
            logging.getLogger().addHandler(handler)
            self._log_handler = handler

    def append_log(self, level: str, source: str, message: str) -> None:
        with self._lock:
            self._log_entries.append(
                {
                    "id": next(self._log_counter),
                    "timestamp": datetime.now().isoformat(timespec="seconds"),
                    "level": level.upper(),
                    "source": source,
                    "message": message,
                }
            )

    def record_pipeline(self, stage: str, status: str, message: str, details: dict[str, Any] | None = None) -> None:
        event = {
            "id": next(self._event_counter),
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "stage": stage,
            "status": status,
            "message": message,
            "details": details or {},
        }
        with self._lock:
            self._pipeline_events.append(event)

    def record_component(self, name: str, status: str, message: str, details: dict[str, Any] | None = None) -> None:
        with self._lock:
            self._component_notes[name] = {
                "status": status,
                "message": message,
                "details": details or {},
                "updated_at": datetime.now().isoformat(timespec="seconds"),
            }

    def record_result(self, payload: dict[str, Any]) -> None:
        with self._lock:
            self._last_result = payload

    def get_logs(self, since_id: int = 0, limit: int = 80) -> list[dict[str, Any]]:
        with self._lock:
            items = [item for item in self._log_entries if item["id"] > since_id]
        return items[-limit:]

    def get_pipeline_events(self, since_id: int = 0, limit: int = 40) -> list[dict[str, Any]]:
        with self._lock:
            items = [item for item in self._pipeline_events if item["id"] > since_id]
        return items[-limit:]

    def get_runtime_log_tails(self, max_lines: int = 30) -> dict[str, list[str]]:
        tails: dict[str, list[str]] = {}
        if not self.runtime_logs_dir.exists():
            return tails

        for path in sorted(self.runtime_logs_dir.glob("*.log")):
            try:
                lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
            except OSError:
                continue
            tails[path.stem] = lines[-max_lines:]
        return tails

    def build_snapshot(self) -> dict[str, Any]:
        recent_results, score_trend = self._recent_results()
        return {
            "app": self._app_snapshot(),
            "host": self._host_snapshot(),
            "stack": self._stack_snapshot(),
            "models": self._model_snapshot(),
            "hardware": self._hardware_snapshot(),
            "storage": self._storage_snapshot(recent_results, score_trend),
            "cloud": self._cloud_snapshot(),
            "pipeline": self._pipeline_snapshot(),
            "last_result": self._last_result_snapshot(),
            "updated_at": datetime.now().isoformat(timespec="seconds"),
        }

    def _app_snapshot(self) -> dict[str, Any]:
        return {
            "name": APP_CONFIG["app_name"],
            "version": APP_CONFIG["version"],
            "mode": "raspberry-pi" if IS_RASPBERRY_PI else "desktop",
            "uptime_seconds": int(max(0, time.time() - self.started_at)),
            "pid": os.getpid(),
            "python": platform.python_version(),
        }

    def _host_snapshot(self) -> dict[str, Any]:
        total_mem = used_mem = mem_percent = None
        meminfo = self._read_meminfo()
        if meminfo:
            total_mem = meminfo.get("MemTotal")
            available_mem = meminfo.get("MemAvailable")
            if total_mem and available_mem is not None:
                used_mem = max(total_mem - available_mem, 0)
                mem_percent = round((used_mem / total_mem) * 100.0, 1) if total_mem else None

        disk = shutil.disk_usage(PATHS["project_root"])
        try:
            load_values = os.getloadavg() if hasattr(os, "getloadavg") else ()
            load = [round(value, 2) for value in load_values]
        except OSError:
            load = []

        return {
            "hostname": socket.gethostname(),
            "ip_address": self._local_ip_address(),
            "platform": platform.platform(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "load_average": load,
            "temperature_c": self._read_temperature(),
            "memory": {
                "total_mb": self._to_mb(total_mem),
                "used_mb": self._to_mb(used_mem),
                "percent": mem_percent,
            },
            "disk": {
                "total_gb": round(disk.total / (1024**3), 2),
                "used_gb": round((disk.total - disk.free) / (1024**3), 2),
                "percent": round(((disk.total - disk.free) / max(disk.total, 1)) * 100.0, 1),
            },
        }

    def _stack_snapshot(self) -> dict[str, Any]:
        cloud_port = int(os.environ.get("INKPI_CLOUD_PORT", "5001"))
        web_port = int(os.environ.get("INKPI_WEB_PORT", str(APP_CONFIG["server"]["port"])))
        return {
            "web_ui": {
                "running": True,
                "healthy": True,
                "pid": os.getpid(),
                "message": f"Listening on 0.0.0.0:{web_port}",
            },
            "cloud_api": self._process_snapshot(
                "cloud_api",
                f"http://127.0.0.1:{cloud_port}/api/health",
                default_message="Cloud API is not active.",
            ),
            "qt_ui": self._process_snapshot(
                "qt_ui",
                None,
                default_message="Qt client is not active.",
            ),
        }

    def _model_snapshot(self) -> dict[str, Any]:
        from services.local_ocr_service import local_ocr_service
        from services.quality_scorer_service import quality_scorer_service

        scorer_status = quality_scorer_service.get_model_status()
        return {
            "ocr": {
                "local_ready": bool(getattr(local_ocr_service, "_available", False)),
                "remote_ready": bool(local_ocr_service.remote_available),
                "overall_ready": bool(local_ocr_service.available),
                "language": local_ocr_service.language,
                "device": local_ocr_service.device,
                "backend_url": local_ocr_service.remote_backend_url or None,
            },
            "quality_scorer": {
                "ready": bool(quality_scorer_service.available),
                "models": scorer_status,
                "input_size": int(quality_scorer_service.input_size),
                "labels": quality_scorer_service.labels,
            },
            "dimension_scorer": {
                "ready": True,
                "rubric_mode": "source-backed-five-dimension",
                "rubrics": {
                    "regular": ["笔法点画", "结体字法", "布白章法", "墨法笔力", "规范完整"],
                    "running": ["用笔线质", "结体取势", "连带节奏", "墨气笔力", "规范识别"],
                },
            },
        }

    def _hardware_snapshot(self) -> dict[str, Any]:
        from services.camera_service import camera_service
        from services.led_service import led_service
        from services.speech_service import speech_service

        try:
            camera_indexes = camera_service.list_cameras()
        except Exception as exc:  # noqa: BLE001
            camera_indexes = []
            self.record_component("camera", "error", "Camera enumeration failed.", {"error": str(exc)})

        spi_devices = list(Path("/dev").glob("spidev*"))
        i2c_devices = list(Path("/dev").glob("i2c-*"))

        return {
            "camera": {
                "healthy": bool(camera_indexes),
                "available_indexes": camera_indexes,
                "opened": bool(camera_service.is_opened),
                "backend": camera_service.config.get("backend", "auto"),
                "message": "Camera ready." if camera_indexes else "No camera detected.",
            },
            "audio": {
                "healthy": bool(speech_service.audio_available),
                "message": speech_service.disabled_reason or "Audio output ready.",
            },
            "led": {
                "healthy": bool(led_service.available),
                "message": led_service.disabled_reason or "LED controller ready.",
            },
            "gpio": {
                "healthy": Path("/dev/gpiomem").exists(),
                "message": "GPIO memory mapped." if Path("/dev/gpiomem").exists() else "GPIO device missing.",
            },
            "spi": {
                "healthy": bool(spi_devices),
                "message": "SPI device detected." if spi_devices else "No SPI device detected.",
            },
            "i2c": {
                "healthy": bool(i2c_devices),
                "message": "I2C bus detected." if i2c_devices else "No I2C bus detected.",
            },
        }

    def _storage_snapshot(self, recent_results: list[dict[str, Any]], score_trend: list[dict[str, Any]]) -> dict[str, Any]:
        image_count = len(list((DATA_DIR / "images").glob("*")))
        processed_count = len(list((DATA_DIR / "processed").glob("*")))
        return {
            "database_path": str(DB_PATH),
            "database_exists": DB_PATH.exists(),
            "database_size_kb": round(DB_PATH.stat().st_size / 1024.0, 1) if DB_PATH.exists() else 0.0,
            "images": image_count,
            "processed_images": processed_count,
            "recent_results": recent_results,
            "score_trend": score_trend,
        }

    def _cloud_snapshot(self) -> dict[str, Any]:
        from services.cloud_sync_service import cloud_sync_service

        backend_url = cloud_sync_service.backend_url
        remote_health = None
        if backend_url:
            remote_health = self._http_health(f"{backend_url}/api/health", cache_key="remote_cloud")

        return {
            "configured": bool(cloud_sync_service.is_ready),
            "device_name": cloud_sync_service.device_name,
            "backend_url": backend_url or None,
            "timeout_seconds": cloud_sync_service.timeout,
            "remote_health": remote_health,
        }

    def _pipeline_snapshot(self) -> dict[str, Any]:
        with self._lock:
            components = dict(self._component_notes)
        return {
            "recent": self.get_pipeline_events(limit=18),
            "components": components,
        }

    def _last_result_snapshot(self) -> dict[str, Any] | None:
        with self._lock:
            return dict(self._last_result) if self._last_result else None

    def _recent_results(self) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        from services.database_service import database_service

        recent_results = []
        for item in database_service.get_recent(8):
            recent_results.append(
                {
                    "id": item.id,
                    "character_name": item.character_name,
                    "script": item.get_script(),
                    "script_label": item.get_script_label(),
                    "total_score": item.total_score,
                    "quality_level": item.quality_level,
                    "timestamp": item.timestamp.isoformat() if item.timestamp else None,
                    "rubric_family": item.get_rubric_family(),
                    "rubric_items": item.get_rubric_items(),
                    "is_legacy_standard": item.is_legacy_standard(),
                }
            )
        return recent_results, database_service.get_score_trend(limit=12)

    def _process_snapshot(self, name: str, health_url: str | None, default_message: str) -> dict[str, Any]:
        pid_file = self.runtime_pids_dir / f"{name}.pid"
        pid = None
        running = False
        if pid_file.exists():
            try:
                pid = int(pid_file.read_text(encoding="utf-8").strip())
                os.kill(pid, 0)
                running = True
            except Exception:
                pid = None
                running = False

        health = self._http_health(health_url, cache_key=name) if health_url else None
        healthy = bool(health and health.get("ok")) if health_url else running
        message = default_message
        if running and health_url and healthy:
            message = f"{name} is healthy."
        elif running:
            message = f"{name} process is running."

        return {
            "pid": pid,
            "running": running,
            "healthy": healthy,
            "message": message,
            "health": health,
        }

    def _http_health(self, url: str | None, cache_key: str, ttl: float = 4.0) -> dict[str, Any] | None:
        if not url:
            return None

        now = time.time()
        cached = self._http_cache.get(cache_key)
        if cached and now - cached[0] < ttl:
            return cached[1]

        try:
            response = requests.get(url, timeout=0.8)
            payload = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
            result = {
                "ok": response.ok,
                "status_code": response.status_code,
                "payload": payload,
            }
        except Exception as exc:  # noqa: BLE001
            result = {
                "ok": False,
                "status_code": None,
                "payload": {"error": str(exc)},
            }

        self._http_cache[cache_key] = (now, result)
        return result

    @staticmethod
    def _read_meminfo() -> dict[str, int]:
        meminfo: dict[str, int] = {}
        path = Path("/proc/meminfo")
        if not path.exists():
            return meminfo
        try:
            for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
                if ":" not in line:
                    continue
                key, raw_value = line.split(":", 1)
                parts = raw_value.strip().split()
                if not parts:
                    continue
                try:
                    meminfo[key] = int(parts[0])
                except ValueError:
                    continue
        except OSError:
            return {}
        return meminfo

    @staticmethod
    def _read_temperature() -> float | None:
        temp_path = Path("/sys/class/thermal/thermal_zone0/temp")
        if not temp_path.exists():
            return None
        try:
            return round(int(temp_path.read_text(encoding="utf-8").strip()) / 1000.0, 1)
        except (OSError, ValueError):
            return None

    @staticmethod
    def _local_ip_address() -> str | None:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                sock.connect(("8.8.8.8", 80))
                return sock.getsockname()[0]
        except OSError:
            try:
                return socket.gethostbyname(socket.gethostname())
            except OSError:
                return None

    @staticmethod
    def _to_mb(value_kb: int | None) -> float | None:
        if value_kb is None:
            return None
        return round(value_kb / 1024.0, 1)


operations_monitor_service = OperationsMonitorService()
