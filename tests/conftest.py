from datetime import UTC, datetime, timedelta

import pytest
from flask_jwt_extended import create_access_token
from werkzeug.security import generate_password_hash

from api import register_blueprints
from cli import register_cli_commands
from database import create_app
from database.extensions import db
from database.models.role import Role
from database.models.user import User
from database.models.user_session import UserSession


@pytest.fixture
def app():
    app = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "JWT_SECRET_KEY": "test-only-secret-key-material-at-least-32-characters",
            "RATELIMIT_ENABLED": False,
        }
    )
    assert app.config["SQLALCHEMY_DATABASE_URI"].startswith("sqlite:")

    register_blueprints(app)
    register_cli_commands(app)

    with app.app_context():
        db.create_all()
        admin_role = Role(role_name="ADMIN", description="System administrator")
        db.session.add(admin_role)
        db.session.flush()
        admin = User(
            username="test-admin",
            password=generate_password_hash("test-admin-password-123"),
            role_id=admin_role.role_id,
            status="ACTIVE",
        )
        db.session.add(admin)
        db.session.commit()
        app.config["TEST_ADMIN_ID"] = admin.user_id
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    client = app.test_client()
    with app.app_context():
        session = UserSession(
            user_id=app.config["TEST_ADMIN_ID"],
            expires_at=datetime.now(UTC) + timedelta(days=30),
        )
        db.session.add(session)
        db.session.flush()
        token = create_access_token(
            identity=str(app.config["TEST_ADMIN_ID"]),
            additional_claims={"sid": session.session_id},
        )
        db.session.commit()
    client.environ_base["HTTP_AUTHORIZATION"] = f"Bearer {token}"
    return client


@pytest.fixture
def unauthenticated_client(app):
    return app.test_client()
