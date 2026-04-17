"""Flask application factory."""

from __future__ import annotations

import os
from pathlib import Path

from flask import Flask


def create_app() -> Flask:
    pkg = Path(__file__).resolve().parent
    root = pkg.parent
    instance = root / "instance"
    instance.mkdir(parents=True, exist_ok=True)

    app = Flask(
        __name__,
        instance_path=str(instance),
        template_folder=str(pkg / "templates"),
        static_folder=str(pkg / "static"),
    )
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-change-in-production")

    from . import routes

    app.register_blueprint(routes.bp)

    return app
