"""Local reference photo enrollment and on-demand matching."""

from __future__ import annotations

import io
from pathlib import Path
from typing import Optional, Tuple

from PIL import Image


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def reference_dir() -> Path:
    return project_root() / "reference"


def reference_path() -> Path:
    return reference_dir() / "me.jpg"


def last_test_path() -> Path:
    return reference_dir() / "last_test.jpg"


def ensure_reference_dir() -> Path:
    d = reference_dir()
    d.mkdir(parents=True, exist_ok=True)
    return d


def save_reference_jpeg(jpeg: bytes) -> Path:
    ensure_reference_dir()
    path = reference_path()
    path.write_bytes(jpeg)
    return path


def save_last_test_jpeg(jpeg: bytes) -> Path:
    ensure_reference_dir()
    path = last_test_path()
    path.write_bytes(jpeg)
    return path


def _dhash(image: Image.Image, size: int = 8) -> int:
    # Resize to (size+1, size) so we can compare neighbors horizontally.
    img = image.convert("L").resize((size + 1, size), Image.Resampling.LANCZOS)
    pixels = list(img.getdata())
    rows = [pixels[i * (size + 1) : (i + 1) * (size + 1)] for i in range(size)]
    bits = []
    for row in rows:
        for c in range(size):
            bits.append(1 if row[c] > row[c + 1] else 0)
    h = 0
    for b in bits:
        h = (h << 1) | b
    return h


def _hamming(a: int, b: int) -> int:
    return (a ^ b).bit_count()


def _pillow_match(ref: Image.Image, cur: Image.Image) -> bool:
    # dHash is lightweight and works reasonably for “same view” comparisons.
    # Threshold tuned for one-user reference matching (Pi-friendly).
    dist = _hamming(_dhash(ref), _dhash(cur))
    return dist <= 12


def _opencv_orb_match(ref_jpeg: bytes, cur_jpeg: bytes) -> Optional[bool]:
    try:
        import cv2  # type: ignore
        import numpy as np  # type: ignore
    except Exception:
        return None

    ref_arr = np.frombuffer(ref_jpeg, dtype=np.uint8)
    cur_arr = np.frombuffer(cur_jpeg, dtype=np.uint8)
    ref = cv2.imdecode(ref_arr, cv2.IMREAD_GRAYSCALE)
    cur = cv2.imdecode(cur_arr, cv2.IMREAD_GRAYSCALE)
    if ref is None or cur is None:
        return None

    ref = cv2.resize(ref, (320, 240), interpolation=cv2.INTER_AREA)
    cur = cv2.resize(cur, (320, 240), interpolation=cv2.INTER_AREA)

    orb = cv2.ORB_create(500)
    kp1, des1 = orb.detectAndCompute(ref, None)
    kp2, des2 = orb.detectAndCompute(cur, None)
    if des1 is None or des2 is None or not kp1 or not kp2:
        return False

    bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
    matches = bf.match(des1, des2)
    matches = sorted(matches, key=lambda m: m.distance)

    good = [m for m in matches if m.distance < 55]
    denom = max(len(kp1), len(kp2), 1)
    ratio = len(good) / denom

    # Conservative: require some absolute + relative evidence.
    return (len(good) >= 20) and (ratio >= 0.12)


def compare_current_to_reference(current_jpeg: bytes) -> Tuple[bool, bool]:
    """
    Returns:
      (match_likely, reference_exists)
    """
    ref_path = reference_path()
    if not ref_path.is_file():
        return False, False

    ref_jpeg = ref_path.read_bytes()

    opencv = _opencv_orb_match(ref_jpeg, current_jpeg)
    if opencv is not None:
        return bool(opencv), True

    # Pillow fallback
    ref_img = Image.open(io.BytesIO(ref_jpeg))
    cur_img = Image.open(io.BytesIO(current_jpeg))
    return _pillow_match(ref_img, cur_img), True

