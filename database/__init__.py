import os
from datetime import timedelta

from dotenv import load_dotenv
from flask import Flask
from flask_cors import CORS
from sqlalchemy import URL

from database.extensions import db, jwt, limiter, migrate


def create_app(config_override=None):
    load_dotenv(override=True)

    app = Flask(__name__)

    database_url = URL.create(
        drivername="postgresql+psycopg",
        username=os.getenv("DB_USER", "").strip(),
        password=os.getenv("DB_PASSWORD", ""),
        host=os.getenv("DB_HOST", "").strip(),
        port=int(os.getenv("DB_PORT", "5432").strip()),
        database=os.getenv("DB_NAME", "").strip(),
    )

    app.config["SQLALCHEMY_DATABASE_URI"] = database_url
    app.config["JWT_SECRET_KEY"] = os.getenv("JWT_SECRET_KEY")
    app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(minutes=15)
    app.config["JWT_REFRESH_TOKEN_EXPIRES"] = timedelta(days=7)
    app.config["AUTH_SESSION_MAX_AGE"] = timedelta(days=30)
    try:
        heartbeat_timeout_seconds = int(
            os.getenv("DEVICE_HEARTBEAT_TIMEOUT_SECONDS", "120")
        )
    except ValueError as error:
        raise RuntimeError(
            "DEVICE_HEARTBEAT_TIMEOUT_SECONDS must be a positive integer"
        ) from error
    if heartbeat_timeout_seconds <= 0:
        raise RuntimeError("DEVICE_HEARTBEAT_TIMEOUT_SECONDS must be a positive integer")
    app.config["DEVICE_HEARTBEAT_TIMEOUT_SECONDS"] = heartbeat_timeout_seconds
    app.config["RATELIMIT_STORAGE_URI"] = os.getenv(
        "RATE_LIMIT_STORAGE_URI", "memory://"
    )
    app.config["RATELIMIT_ENABLED"] = (
        os.getenv("RATELIMIT_ENABLED", "true").strip().lower() == "true"
    )
    app.config["RATELIMIT_HEADERS_ENABLED"] = True
    try:
        max_content_length = int(os.getenv("MAX_CONTENT_LENGTH", "2097152"))
    except ValueError as error:
        raise RuntimeError(
            "MAX_CONTENT_LENGTH must be a positive integer"
        ) from error
    if max_content_length <= 0:
        raise RuntimeError("MAX_CONTENT_LENGTH must be a positive integer")
    app.config["MAX_CONTENT_LENGTH"] = max_content_length
    app.config["JWT_TOKEN_LOCATION"] = ["headers"]
    app.config["JWT_ALGORITHM"] = "HS256"
    app.config["JWT_DECODE_ALGORITHMS"] = ["HS256"]
    if config_override:
        # Test configurations are applied before extensions create their engines.
        app.config.update(config_override)

    jwt_secret = app.config.get("JWT_SECRET_KEY")
    if not isinstance(jwt_secret, str) or len(jwt_secret) < 32:
        raise RuntimeError(
            "JWT_SECRET_KEY must be configured with at least 32 characters"
        )

    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    limiter.init_app(app)

    from api.responses import error_response

    @app.errorhandler(413)
    def _payload_too_large(error):
        return error_response("Request payload too large", 413)

    @app.errorhandler(429)
    def _rate_limit_exceeded(error):
        return error_response("Too many requests. Please try again later.", 429)

    allowed_origins = [
        origin.strip()
        for origin in os.getenv("CORS_ALLOWED_ORIGINS", "").split(",")
        if origin.strip()
    ]

    if allowed_origins:
        CORS(
            app,
            origins=allowed_origins,
            allow_headers=["Content-Type", "Authorization", "X-Device-Key"],
            methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        )

    from api.assistance.routes import assistance_bp  # noqa: F401
    from database.models import (
        assistance_request,  # noqa: F401
        device_status_log,  # noqa: F401
        occupancy_event,  # noqa: F401
        profile,  # noqa: F401
        refresh_token,  # noqa: F401
        role,  # noqa: F401
        room,  # noqa: F401
        room_device,  # noqa: F401
        user,  # noqa: F401
        user_session,  # noqa: F401
    )

    return app
