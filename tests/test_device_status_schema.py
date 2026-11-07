import pytest
from sqlalchemy.exc import IntegrityError

from database.extensions import db
from database.models.device_status_log import DeviceStatusLog
from database.models.room import Room
from database.models.room_device import RoomDevice


def _registered_device():
    room = Room(room_number="101", room_name="Room 101")
    db.session.add(room)
    db.session.flush()
    device = RoomDevice(
        device_id="DEV001",
        room_id=room.room_id,
        device_code="SENSOR-001",
        registration_status="REGISTERED",
        credential_hash="a" * 64,
    )
    db.session.add(device)
    db.session.flush()
    return device


def test_device_connectivity_state_and_status_history_relationship(app):
    with app.app_context():
        device = _registered_device()
        assert device.current_status == "UNKNOWN"
        assert device.last_communication_at is None

        db.session.add(
            DeviceStatusLog(
                device_id=device.device_id,
                previous_status="UNKNOWN",
                new_status="ONLINE",
                reason="HEARTBEAT",
            )
        )
        db.session.commit()

        assert len(device.status_history) == 1
        assert device.status_history[0].new_status == "ONLINE"
        assert device.status_history[0].reason == "HEARTBEAT"


def test_device_status_check_constraints_reject_invalid_values(app):
    with app.app_context():
        device = _registered_device()
        device.current_status = "CONNECTED"
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()


def test_device_status_history_requires_a_real_transition(app):
    with app.app_context():
        device = _registered_device()
        db.session.add(
            DeviceStatusLog(
                device_id=device.device_id,
                previous_status="ONLINE",
                new_status="ONLINE",
                reason="HEARTBEAT",
            )
        )
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()
