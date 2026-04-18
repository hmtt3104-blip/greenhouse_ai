"""
Periodic person detection using OpenCV HOG (lightweight on Raspberry Pi 4).

Runs in a daemon thread: grabs frames via the existing CameraStream, detects people,
saves snapshots under alerts/, sends Telegram photos when configured, enforces cooldown.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger(__name__)

ALERT_COOLDOWN_SEC = 60.0
DETECTION_INTERVAL_SEC_DEFAULT = 3.0
ALERT_MESSAGE = "Person detected by greenhouse camera"

_state_lock = threading.Lock()
_detection_enabled = True
_opencv_available: bool | None = None
_last_detection_iso: str | None = None
_worker_started = False


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def alerts_dir() -> Path:
    return project_root() / "alerts"


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, "").strip() or default)
    except ValueError:
        return default


def _env_bool(name: str, default: bool) -> bool:
    v = os.environ.get(name, "").strip().lower()
    if not v:
        return default
    return v in ("1", "true", "yes", "on")


def person_detection_enabled() -> bool:
    return _env_bool("PERSON_DETECTION_ENABLED", True)


def detection_interval_sec() -> float:
    return max(1.0, _env_float("PERSON_DETECTION_INTERVAL_SEC", DETECTION_INTERVAL_SEC_DEFAULT))


def alert_cooldown_sec() -> float:
    return max(1.0, _env_float("PERSON_ALERT_COOLDOWN_SEC", ALERT_COOLDOWN_SEC))


def get_public_status() -> dict:
    """Snapshot for /api/detection/status."""
    global _opencv_available
    with _state_lock:
        last = _last_detection_iso
        ocv = _opencv_available
    return {
        "detection_enabled": person_detection_enabled(),
        "opencv_available": ocv,
        "interval_sec": detection_interval_sec(),
        "cooldown_sec": alert_cooldown_sec(),
        "last_detection_time": last,
        "worker_running": _worker_started,
    }


def _set_last_detection(iso: str) -> None:
    global _last_detection_iso
    with _state_lock:
        _last_detection_iso = iso


def _try_import_cv2():
    global _opencv_available
    if _opencv_available is not None:
        return _opencv_available
    try:
        import cv2  # noqa: F401

        _opencv_available = True
    except ImportError:
        _opencv_available = False
        log.warning(
            "OpenCV not available — person detection disabled. "
            "Install: sudo apt install python3-opencv"
        )
    return _opencv_available


def _detect_person_hog(jpeg_bytes: bytes) -> bool:
    import cv2
    import numpy as np

    arr = np.frombuffer(jpeg_bytes, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        return False
    h, w = img.shape[:2]
    if w > 640:
        scale = 640.0 / float(w)
        img = cv2.resize(
            img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA
        )
    hog = cv2.HOGDescriptor()
    hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())
    rects, weights = hog.detectMultiScale(
        img,
        winStride=(8, 8),
        padding=(8, 8),
        scale=1.05,
        hitThreshold=0.0,
    )
    if len(rects) == 0:
        return False
    if weights is not None and len(weights):
        return float(weights.max()) >= 0.25
    return True


def _save_alert_snapshot(jpeg: bytes) -> Path:
    alerts_dir().mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    path = alerts_dir() / f"person_{ts}.jpg"
    path.write_bytes(jpeg)
    return path


def _worker_loop(instance_path: Path) -> None:
    global _worker_started
    from camera.stream import get_camera_stream
    from dashboard.telegram_config import load_settings, send_photo

    last_alert_monotonic = 0.0
    cooldown = alert_cooldown_sec()

    log.info(
        "Person detection worker started (interval=%.1fs, cooldown=%.1fs)",
        detection_interval_sec(),
        cooldown,
    )

    while True:
        interval = detection_interval_sec()
        try:
            if not person_detection_enabled():
                time.sleep(interval)
                continue

            if not _try_import_cv2():
                time.sleep(60.0)
                continue

            stream = get_camera_stream()
            jpeg = stream.capture_jpeg_now()

            if _detect_person_hog(jpeg):
                now_m = time.monotonic()
                if now_m - last_alert_monotonic < cooldown:
                    log.debug("Person-like detection during cooldown; skipping alert")
                    time.sleep(interval)
                    continue

                log.info("Person detection: candidate match — processing alert")

                path = _save_alert_snapshot(jpeg)
                iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                _set_last_detection(iso)
                last_alert_monotonic = now_m

                log.info("Person alert: snapshot saved path=%s", path)

                settings = load_settings(instance_path)
                token = str(settings.get("bot_token") or "").strip()
                chat = str(settings.get("chat_id") or "").strip()
                alerts_explicitly_off = os.environ.get(
                    "TELEGRAM_ALERTS_ENABLED", ""
                ).strip().lower() in ("0", "false", "no")

                if token and chat and not alerts_explicitly_off:
                    log.info("Sending Telegram photo alert")
                    ok, msg = send_photo(
                        token,
                        chat,
                        jpeg,
                        filename="person.jpg",
                        caption=ALERT_MESSAGE,
                    )
                    if ok:
                        log.info("Telegram person alert sent successfully")
                    else:
                        log.warning("Telegram person alert failed: %s", msg)
                elif token and chat and alerts_explicitly_off:
                    log.info(
                        "TELEGRAM_ALERTS_ENABLED disables outbound Telegram; snapshot kept locally only"
                    )
                else:
                    log.info(
                        "Telegram not configured (TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID); "
                        "snapshot kept locally only"
                    )
        except Exception:
            log.exception("Person detection loop error")
        time.sleep(interval)


def start_person_detection_background(instance_path: Path) -> None:
    global _worker_started
    if _worker_started:
        return
    t = threading.Thread(
        target=_worker_loop,
        args=(instance_path,),
        name="person-detection",
        daemon=True,
    )
    _worker_started = True
    t.start()
