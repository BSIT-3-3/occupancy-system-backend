import os
from dotenv import load_dotenv
from flask import Flask
from database.extensions import db, migrate

load_dotenv()

def create_app():
    app = Flask(__name__)

    app.config["SQLALCHEMY_DATABASE_URI"] = (
        f"postgresql+psycopg://"
        f"{os.getenv('DB_USER')}:"
        f"{os.getenv('DB_PASSWORD')}@"
        f"{os.getenv('DB_HOST')}:"
        f"{os.getenv('DB_PORT')}/"
        f"{os.getenv('DB_NAME')}"
    )

    db.init_app(app)
    migrate.init_app(app, db)

    return app

