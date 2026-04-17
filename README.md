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

On a Raspberry Pi, install OS-level dependencies (e.g. camera stack) as needed for your hardware.
