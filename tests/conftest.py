import pytest

from api.authentication.routes import auth_bp
from database import create_app
from database.extensions import db
from database.models.room import Room
from database.models.room_device import RoomDevice
from services.authentication.user import users_bp
from services.authentication.user_profile import profiles_bp
from services.role.role import roles_bp


@pytest.fixture
def app():
    app = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
        }
    )

    # Register additional blueprints
    # Occupancy, device, and gateway are already registered by create_app()
    app.register_blueprint(auth_bp)
    app.register_blueprint(roles_bp)
    app.register_blueprint(users_bp)
    app.register_blueprint(profiles_bp)

    with app.app_context():
        db.create_all()

        yield app

        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def occupancy_data(app):
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
        )

        db.session.add(device)
        db.session.commit()

        return {
            "room_id": room.room_id,
            "device_id": device.device_id,
        }
