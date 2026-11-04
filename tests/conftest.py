import hashlib

import pytest
from flask_jwt_extended import create_access_token
from werkzeug.security import generate_password_hash

from api import register_blueprints
from cli import register_cli_commands
from database import create_app
from database.extensions import db
from database.models.role import Role
from database.models.room import Room
from database.models.room_device import RoomDevice
from database.models.user import User


@pytest.fixture
def app():
    app = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "JWT_SECRET_KEY": ("test-only-secret-key-material-at-least-32-characters"),
        }
    )

    register_blueprints(app)
    register_cli_commands(app)

    with app.app_context():
        db.create_all()

        admin_role = Role(
            role_name="ADMIN",
            description="System administrator",
        )
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
        token = create_access_token(identity=str(app.config["TEST_ADMIN_ID"]))

    client.environ_base["HTTP_AUTHORIZATION"] = f"Bearer {token}"

    return client


@pytest.fixture
def unauthenticated_client(app):
    return app.test_client()


@pytest.fixture
def occupancy_data(app):
    device_key = "test-device-secret-key-12345"

    with app.app_context():
        room = Room(
            room_number="TEST-ROOM-001",
            room_name="Test Room",
            occupancy_status="AVAILABLE",
            is_active=True,
        )

        db.session.add(room)
        db.session.flush()

        device = RoomDevice(
            device_id="TEST-DEV-001",
            room_id=room.room_id,
            device_code="TEST-CODE-001",
            device_name="Test Device",
            registration_status="REGISTERED",
            credential_hash=hashlib.sha256(device_key.encode("utf-8")).hexdigest(),
        )

        db.session.add(device)
        db.session.commit()

        return {
            "room_id": room.room_id,
            "device_id": device.device_id,
            "device_key": device_key,
        }
