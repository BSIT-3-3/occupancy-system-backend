import os
from datetime import timedelta

from dotenv import load_dotenv
from flask import Flask
from flask_cors import CORS
from sqlalchemy import URL

from database.extensions import db, jwt, migrate


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
    app.config["JWT_TOKEN_LOCATION"] = ["headers"]
    app.config["JWT_ALGORITHM"] = "HS256"
    app.config["JWT_DECODE_ALGORITHMS"] = ["HS256"]

    if config_override:
        app.config.update(config_override)

    jwt_secret = app.config.get("JWT_SECRET_KEY")
    if not isinstance(jwt_secret, str) or len(jwt_secret) < 32:
        raise RuntimeError(
            "JWT_SECRET_KEY must be configured with at least 32 characters"
        )

    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)

    allowed_origins = [
        origin.strip()
        for origin in os.getenv("CORS_ALLOWED_ORIGINS", "").split(",")
        if origin.strip()
    ]

    if allowed_origins:
        CORS(
            app,
            origins=allowed_origins,
            allow_headers=[
                "Content-Type",
                "Authorization",
                "X-Device-Key",
            ],
            methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        )

    from api.assistance.routes import assistance_bp
    from api.device_management.routes import device_bp
    from api.gateway.routes import gateway_bp
    from api.occupancy.routes import occupancy_bp
    from database.models import (
        assistance_request,  # noqa: F401
        occupancy_event,  # noqa: F401
        profile,  # noqa: F401
        role,  # noqa: F401
        room,  # noqa: F401
        room_device,  # noqa: F401
        user,  # noqa: F401
    )

    app.register_blueprint(assistance_bp)
    app.register_blueprint(device_bp)
    app.register_blueprint(occupancy_bp)
    app.register_blueprint(gateway_bp)

    return app
