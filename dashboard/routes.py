"""Dashboard routes: camera, sensors, Telegram."""

from __future__ import annotations

import logging
from pathlib import Path

from flask import (
    Blueprint,
    Response,
    abort,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)

from camera.stream import get_camera_stream
from dashboard.reference_flow import (
    compare_current_to_reference,
    ensure_reference_dir,
    last_test_path,
    reference_path,
    save_last_test_jpeg,
    save_reference_jpeg,
)
from dashboard.telegram_config import (
    load_settings,
    mask_token_display,
    save_settings,
    send_message,
)
from sensors.service import get_sensor_service

bp = Blueprint("main", __name__)
log = logging.getLogger(__name__)


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

@bp.route("/reference/me.jpg")
def reference_image():
    path = reference_path()
    if not path.is_file():
        abort(404)
    return send_file(path, mimetype="image/jpeg", conditional=True)


@bp.route("/reference/last_test.jpg")
def last_test_image():
    path = last_test_path()
    if not path.is_file():
        abort(404)
    return send_file(path, mimetype="image/jpeg", conditional=True)


@bp.route("/api/reference/capture", methods=["POST"])
def api_reference_capture():
    ensure_reference_dir()
    stream = get_camera_stream()
    jpeg = stream.capture_jpeg_now()
    out = save_reference_jpeg(jpeg)
    log.info("reference photo saved: %s", out)
    return jsonify(
        {
            "ok": True,
            "message": "reference photo saved",
            "reference_url": url_for("main.reference_image"),
        }
    )


@bp.route("/api/reference/test", methods=["POST"])
def api_reference_test():
    stream = get_camera_stream()
    jpeg = stream.capture_jpeg_now()
    save_last_test_jpeg(jpeg)

    log.info("comparison started")
    match, has_ref = compare_current_to_reference(jpeg)
    if not has_ref:
        msg = "no reference match"
        log.info("comparison result: %s (no reference file)", msg)
        return jsonify(
            {
                "ok": True,
                "message": msg,
                "reference_exists": False,
                "test_url": url_for("main.last_test_image"),
            }
        )

    msg = "reference match likely" if match else "no reference match"
    log.info("comparison result: %s", msg)
    return jsonify(
        {
            "ok": True,
            "message": msg,
            "reference_exists": True,
            "reference_url": url_for("main.reference_image"),
            "test_url": url_for("main.last_test_image"),
        }
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
