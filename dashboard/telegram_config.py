"""Load/save Telegram bot settings and send test messages via Bot API."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import requests


def _config_path(instance_path: Path) -> Path:
    return instance_path / "telegram.json"


def load_settings(instance_path: Path) -> dict[str, Any]:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    enabled = os.environ.get("TELEGRAM_ALERTS_ENABLED", "").lower() in (
        "1",
        "true",
        "yes",
        "on",
    )
    data: dict[str, Any] = {
        "bot_token": token,
        "chat_id": chat_id,
        "enabled": enabled,
    }
    path = _config_path(instance_path)
    if path.is_file():
        try:
            file_data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(file_data, dict):
                if file_data.get("bot_token"):
                    data["bot_token"] = str(file_data["bot_token"]).strip()
                if file_data.get("chat_id") is not None:
                    data["chat_id"] = str(file_data["chat_id"]).strip()
                if "enabled" in file_data:
                    data["enabled"] = bool(file_data["enabled"])
        except (OSError, json.JSONDecodeError):
            pass
    if token:
        data["bot_token"] = token
    if chat_id:
        data["chat_id"] = chat_id
    return data


def save_settings(
    instance_path: Path,
    bot_token: str,
    chat_id: str,
    enabled: bool,
) -> None:
    instance_path.mkdir(parents=True, exist_ok=True)
    path = _config_path(instance_path)
    payload = {
        "bot_token": bot_token.strip(),
        "chat_id": chat_id.strip(),
        "enabled": enabled,
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def mask_token_display(settings: dict[str, Any]) -> dict[str, Any]:
    t = str(settings.get("bot_token", ""))
    if len(t) > 10:
        display = f"{t[:4]}…{t[-4:]}"
    elif t:
        display = "…" + t[-min(4, len(t)) :]
    else:
        display = ""
    out = dict(settings)
    out["bot_token"] = ""
    out["bot_token_display"] = display
    out["has_token"] = bool(t)
    return out


def send_photo(
    bot_token: str,
    chat_id: str,
    image_bytes: bytes,
    *,
    filename: str = "snapshot.jpg",
    caption: str = "",
) -> tuple[bool, str]:
    """Send a photo via Telegram Bot API (multipart)."""
    if not bot_token or not chat_id:
        return False, "Set bot token and chat ID first."
    url = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
    files = {"photo": (filename, image_bytes, "image/jpeg")}
    data: dict[str, Any] = {"chat_id": chat_id}
    if caption:
        data["caption"] = caption
    try:
        r = requests.post(url, data=data, files=files, timeout=90)
    except requests.RequestException as e:
        return False, str(e)
    if r.ok:
        return True, "Photo sent."
    try:
        err = r.json()
    except Exception:
        err = r.text[:300]
    return False, f"HTTP {r.status_code}: {err}"


def send_message(bot_token: str, chat_id: str, text: str) -> tuple[bool, str]:
    if not bot_token or not chat_id:
        return False, "Set bot token and chat ID first."
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    try:
        r = requests.post(
            url,
            json={"chat_id": chat_id, "text": text},
            timeout=20,
        )
    except requests.RequestException as e:
        return False, str(e)
    if r.ok:
        return True, "Message sent."
    try:
        err = r.json()
    except Exception:
        err = r.text[:300]
    return False, f"HTTP {r.status_code}: {err}"
