import os

from dotenv import load_dotenv
from flask import Flask
from sqlalchemy import URL

from database.extensions import db, migrate


def create_app():
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

    db.init_app(app)
    migrate.init_app(app, db)

    from database.models import (
        assistance_request,  # noqa: F401
        occupancy_event,  # noqa: F401
        profile,  # noqa: F401
        role,  # noqa: F401
        room,  # noqa: F401
        room_device,  # noqa: F401
        user,  # noqa: F401
    )

    from api.assistance.routes import assistance_bp
    app.register_blueprint(assistance_bp)

    return app
