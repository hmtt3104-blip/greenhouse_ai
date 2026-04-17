"""MJPEG camera stream: Picamera2 on Raspberry Pi, placeholder JPEG otherwise."""

from __future__ import annotations

import io
import logging
import threading
import time
from typing import Any, Generator, Optional

from PIL import Image, ImageDraw

log = logging.getLogger(__name__)

try:
    from picamera2 import Picamera2

    _HAS_PICAMERA2 = True
except ImportError:
    Picamera2 = None  # type: ignore[misc, assignment]
    _HAS_PICAMERA2 = False


def _apply_image_tuning(picam: Any) -> None:
    """
    Brighter, more contrasty preview with auto exposure tuned for dim greenhouse
    conditions: longer exposure budget, long-AE bias, shadow metering, NR.

    Tries several control sets so unsupported keys on a given sensor are skipped.
    """
    # ExposureValue: stops relative to AE target (+ = brighter).
    # FrameDurationLimits (µs): larger max lets AE use longer shutter in low light.
    base: dict[str, Any] = {
        "AeEnable": True,
        "AwbEnable": True,
        "Brightness": 0.14,
        "Contrast": 1.18,
        "Saturation": 1.04,
        "Sharpness": 1.05,
        "ExposureValue": 0.45,
        "FrameDurationLimits": (40000, 280000),
    }

    enums: dict[str, Any] = {}
    try:
        from libcamera import controls as C

        if hasattr(C, "AeExposureModeEnum"):
            enums["AeExposureMode"] = C.AeExposureModeEnum.Long
        if hasattr(C, "AeConstraintModeEnum"):
            enums["AeConstraintMode"] = C.AeConstraintModeEnum.Shadows
        if hasattr(C, "NoiseReductionModeEnum"):
            enums["NoiseReductionMode"] = C.NoiseReductionModeEnum.HighQuality
    except ImportError:
        log.debug("libcamera.controls not available — skipping AE/NR enums")
    except AttributeError:
        log.debug("libcamera enum incomplete — skipping some AE/NR keys")

    def merge(extra: dict[str, Any]) -> dict[str, Any]:
        return {**base, **extra}

    variants: list[dict[str, Any]] = [
        merge(enums),
        merge({k: v for k, v in enums.items() if k != "NoiseReductionMode"}),
        merge(
            {
                k: v
                for k, v in enums.items()
                if k not in ("NoiseReductionMode", "AeConstraintMode")
            }
        ),
        dict(base),
        {
            k: v
            for k, v in base.items()
            if k not in ("FrameDurationLimits", "ExposureValue")
        },
        {k: v for k, v in base.items() if k != "FrameDurationLimits"},
        {
            "AeEnable": True,
            "AwbEnable": True,
            "Brightness": 0.12,
            "Contrast": 1.1,
        },
    ]

    for i, ctrls in enumerate(variants):
        if not ctrls:
            continue
        try:
            picam.set_controls(ctrls)
            log.info("Camera image tuning applied (profile %s)", i)
            return
        except Exception as exc:
            log.debug("Tuning profile %s rejected: %s", i, exc)

    log.warning("Could not apply image tuning — using driver defaults")


class CameraStream:
    """Continuous JPEG capture in a background thread for /video_feed."""

    def __init__(self, fps: float = 12.0) -> None:
        self._fps = fps
        self._lock = threading.Lock()
        self._jpeg: bytes = b""
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._picam: Any = None
        self._mode = "placeholder"

    def start(self) -> None:
        if self._thread is not None:
            return
        if _HAS_PICAMERA2 and Picamera2 is not None:
            for attempt in range(1, 4):
                pic = self._try_open_picamera2()
                if pic is not None:
                    self._picam = pic
                    self._mode = "picamera2"
                    log.info("Picamera2 started (preview RGB888 640x480, tuned for low light)")
                    break
                log.warning("Picamera2 init attempt %s/3 failed", attempt)
                time.sleep(0.35)
            else:
                self._picam = None
                self._mode = "placeholder"
        else:
            log.info("Picamera2 not installed — using placeholder frames")
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def _try_open_picamera2(self) -> Any:
        """Open Picamera2 with RGB888 preview; return None on any failure."""
        picam: Any = None
        try:
            picam = Picamera2()
            picam.configure(
                picam.create_preview_configuration(
                    main={"format": "RGB888", "size": (640, 480)},
                )
            )
            picam.start()
            _apply_image_tuning(picam)
            time.sleep(0.2)
            for _ in range(8):
                picam.capture_array("main")
                time.sleep(0.04)
            return picam
        except Exception as exc:
            log.warning("Picamera2 setup failed: %s", exc)
            if picam is not None:
                try:
                    picam.stop()
                except Exception:
                    pass
                try:
                    picam.close()
                except Exception:
                    pass
            return None

    def _close_picamera2(self) -> None:
        if self._picam is None:
            return
        try:
            self._picam.stop()
        except Exception:
            pass
        try:
            self._picam.close()
        except Exception:
            pass
        self._picam = None

    def _loop(self) -> None:
        interval = 1.0 / max(self._fps, 1.0)
        fails = 0
        while self._running:
            if self._mode == "picamera2" and self._picam is not None:
                try:
                    arr = self._picam.capture_array("main")
                    if hasattr(arr, "ndim") and arr.ndim == 3:
                        ch = arr.shape[2]
                        if ch >= 3:
                            arr = arr[:, :, :3]
                    jpeg = self._array_to_jpeg(arr)
                    fails = 0
                except Exception as exc:
                    fails += 1
                    log.warning("Picamera2 capture failed (%s): %s", fails, exc)
                    jpeg = self._placeholder_frame()
                    if fails >= 15:
                        self._close_picamera2()
                        self._mode = "placeholder"
                        log.warning("Too many capture errors — switched to placeholder")
                        fails = 0
            else:
                jpeg = self._placeholder_frame()
            with self._lock:
                self._jpeg = jpeg
            time.sleep(interval)

    def _array_to_jpeg(self, arr: object) -> bytes:
        from PIL import Image

        img = Image.fromarray(arr)  # type: ignore[arg-type]
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=82, optimize=True)
        return buf.getvalue()

    def _placeholder_frame(self) -> bytes:
        img = Image.new("RGB", (640, 480), color=(18, 32, 22))
        draw = ImageDraw.Draw(img)
        draw.rectangle([0, 0, 639, 479], outline=(60, 110, 75))
        draw.text((120, 200), "greenhouse_ai", fill=(130, 210, 150))
        draw.text(
            (95, 240),
            "No camera / Picamera2 unavailable",
            fill=(100, 160, 120),
        )
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85)
        return buf.getvalue()

    def current_jpeg(self) -> bytes:
        with self._lock:
            if self._jpeg:
                return self._jpeg
        return self._placeholder_frame()

    def mjpeg_generator(self) -> Generator[bytes, None, None]:
        interval = 1.0 / max(self._fps, 1.0)
        while True:
            frame = self.current_jpeg()
            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n"
                + frame
                + b"\r\n"
            )
            time.sleep(interval)


_stream: Optional[CameraStream] = None


def get_camera_stream() -> CameraStream:
    global _stream
    if _stream is None:
        _stream = CameraStream()
        _stream.start()
    return _stream
