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
| Live camera | `/camera` | MJPEG stream at `/video_feed` (Picamera2 on Pi, placeholder otherwise) |
| Reference photo | `/camera` | Capture `reference/me.jpg` with countdown; test on demand and saves `reference/last_test.jpg` |
| Sensors | `/sensors` | JSON API: `/api/sensors` (mock data until hardware is wired) |
| Telegram | `/telegram` | Bot token & chat ID; test via `POST /api/telegram/test` |

Telegram credentials can live in `.env` (`TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`) or in `instance/telegram.json` via the web form.

On a Raspberry Pi, enable the camera stack and install **`picamera2`** (see Raspberry Pi OS docs) for a real live feed.

### Reference matching dependencies (optional)

The project includes a lightweight Pillow hash matcher by default. For better matching on a Raspberry Pi 4 you can install OpenCV:

```bash
sudo apt update
sudo apt install -y python3-opencv
```
