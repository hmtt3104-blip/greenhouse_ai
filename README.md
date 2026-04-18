# greenhouse_ai

Raspberry Pi–based software for monitoring and automating a small greenhouse: camera views, environmental sensors, and a local dashboard.

## Layout

| Path | Purpose |
|------|---------|
| `camera/` | Capture and image pipeline |
| `sensors/` | Hardware drivers and readings |
| `dashboard/` | Web UI and monitoring |
| `scripts/` | One-off tools and maintenance |
| `docs/` | Notes and diagrams |
| `main.py` | Application entry point |

## Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then edit .env
python main.py
```

Open `http://127.0.0.1:5000` on the Pi, or from your LAN use `http://<hostname-or-ip>:5000`. Override host/port with `DASHBOARD_HOST` and `DASHBOARD_PORT`.

### Dashboard (Flask)

| Page | Path | Notes |
|------|------|--------|
| Home | `/` | Links to camera, sensors, Telegram |
| Live camera | `/camera` | MJPEG stream at `/video_feed`; person detection status via `GET /api/detection/status` |
| Reference photo | `/camera` | Capture `reference/me.jpg` with countdown; test on demand and saves `reference/last_test.jpg` |
| Sensors | `/sensors` | JSON API: `/api/sensors` (mock data until hardware is wired) |
| Telegram | `/telegram` | Bot token & chat ID; test via `POST /api/telegram/test` |

Telegram credentials can live in `.env` (`TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`) or in `instance/telegram.json` via the web form.

On a Raspberry Pi, enable the camera stack and install **`picamera2`** (see Raspberry Pi OS docs) for a real live feed.

### OpenCV (recommended on Raspberry Pi)

Used for reference-photo matching (optional ORB path), **person detection** (HOG), and decoding JPEGs. Install system packages on Pi OS:

```bash
sudo apt update
sudo apt install -y python3-opencv
```

Without OpenCV, the dashboard still runs; person detection stays idle and the camera page shows OpenCV unavailable.

### Person detection and Telegram alerts

- **Detection**: background thread samples the camera every `PERSON_DETECTION_INTERVAL_SEC` (default 3). Uses OpenCV **HOG** people detector (lightweight on Pi 4).
- **Snapshots**: saved under `alerts/person_YYYYMMDD_HHMMSS.jpg`.
- **Telegram**: set `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` in `.env` (or use `instance/telegram.json` from the dashboard). Sends a photo with caption `Person detected by greenhouse camera`. If those vars are unset, snapshots are still saved and the app does not crash.
- **Cooldown**: at most one alert (snapshot + Telegram) per `PERSON_ALERT_COOLDOWN_SEC` (default 60).
- **Optional env**: `PERSON_DETECTION_ENABLED=0` to disable detection; `TELEGRAM_ALERTS_ENABLED=0` to suppress Telegram sends while keeping local snapshots.

### Reference matching dependencies (optional)

The project includes a lightweight Pillow hash matcher by default. For better matching on a Raspberry Pi 4 you can use OpenCV ORB when `python3-opencv` is installed (see above).
