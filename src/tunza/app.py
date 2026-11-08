"""Flask application factory."""

from __future__ import annotations

from flask import Flask

from tunza.config import Settings, get_settings
from tunza.db.engine import Database
from tunza.logging import configure_logging
from tunza.web.health import bp as health_bp
from tunza.web.security import add_security_headers

MAX_UPLOAD_BYTES = 10 * 1024 * 1024


def create_app(settings: Settings | None = None) -> Flask:
    """Build the Tunza web application."""

    resolved = settings or get_settings()
    app = Flask(__name__, static_folder="web/static", static_url_path="/static")
    app.config.update(
        APP_ENV=resolved.app_env.value,
        SECRET_KEY=resolved.secret_key.get_secret_value(),
        MAX_CONTENT_LENGTH=MAX_UPLOAD_BYTES,
    )

    configure_logging(resolved)
    app.extensions["tunza.settings"] = resolved
    app.extensions["tunza.db"] = Database(resolved)
    app.register_blueprint(health_bp)
    app.after_request(add_security_headers)
    return app
