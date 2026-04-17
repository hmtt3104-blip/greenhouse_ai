"""Dashboard routes: camera, sensors, Telegram."""

from __future__ import annotations

from pathlib import Path

from flask import (
    Blueprint,
    Response,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)

from camera.stream import get_camera_stream
from dashboard.telegram_config import (
    load_settings,
    mask_token_display,
    save_settings,
    send_message,
)
from sensors.service import get_sensor_service

bp = Blueprint("main", __name__)


@bp.route("/")
def index():
    return render_template("index.html")


@bp.route("/camera")
def camera_page():
    return render_template("camera.html")


@bp.route("/video_feed")
def video_feed():
    stream = get_camera_stream()
    return Response(
        stream.mjpeg_generator(),
        mimetype="multipart/x-mixed-replace; boundary=frame",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
            "X-Accel-Buffering": "no",
        },
    )


@bp.route("/sensors")
def sensors_page():
    return render_template("sensors.html")


@bp.route("/api/sensors")
def api_sensors():
    return jsonify(get_sensor_service().read_all())


@bp.route("/telegram", methods=["GET", "POST"])
def telegram_page():
    inst = Path(current_app.instance_path)
    if request.method == "POST":
        token = request.form.get("bot_token", "").strip()
        chat_id = request.form.get("chat_id", "").strip()
        enabled = request.form.get("enabled") == "on"
        prev = load_settings(inst)
        if not token and prev.get("bot_token"):
            token = str(prev["bot_token"])
        if not chat_id and prev.get("chat_id"):
            chat_id = str(prev["chat_id"])
        save_settings(inst, token, chat_id, enabled)
        flash("Telegram settings saved.", "success")
        return redirect(url_for("main.telegram_page"))

    settings = mask_token_display(load_settings(inst))
    return render_template("telegram.html", settings=settings)


@bp.route("/api/telegram/test", methods=["POST"])
def api_telegram_test():
    inst = Path(current_app.instance_path)
    s = load_settings(inst)
    ok, msg = send_message(
        str(s.get("bot_token", "")),
        str(s.get("chat_id", "")),
        "greenhouse_ai: test message from dashboard.",
    )
    return jsonify({"ok": ok, "message": msg})
