import hashlib

from database.extensions import db
from database.models.room import Room
from database.models.room_device import RoomDevice


def test_occupancy_events_require_a_device_key(app, unauthenticated_client):
    device_key = "device-secret-generated-outside-the-database"
    with app.app_context():
        room = Room(
            room_number="201",
            room_name="Test Room",
            occupancy_status="AVAILABLE",
            is_active=True,
        )
        db.session.add(room)
        db.session.flush()
        db.session.add(
            RoomDevice(
                device_id="TEST-DEVICE",
                room_id=room.room_id,
                device_code="TEST-CODE",
                registration_status="REGISTERED",
                credential_hash=hashlib.sha256(device_key.encode("utf-8")).hexdigest(),
            )
        )
        db.session.commit()
        room_id = room.room_id

    payload = {
        "room_id": room_id,
        "device_id": "TEST-DEVICE",
        "event_type": "MOTION_DETECTED",
        "occupancy_status": "OCCUPIED",
    }
    missing = unauthenticated_client.post("/api/occupancy/events", json=payload)
    assert missing.status_code == 401
    assert missing.json == {"error": "Invalid device credentials"}

    invalid = unauthenticated_client.post(
        "/api/occupancy/events",
        json=payload,
        headers={"X-Device-Key": "wrong-device-key"},
    )
    assert invalid.status_code == 401

    accepted = unauthenticated_client.post(
        "/api/occupancy/events",
        json=payload,
        headers={"X-Device-Key": device_key},
    )
    assert accepted.status_code == 201

    with app.app_context():
        room = db.session.get(Room, room_id)
        assert room.occupancy_status == "OCCUPIED"
        assert room.last_occupancy_update is not None


def test_pending_device_cannot_submit_events(app, unauthenticated_client):
    device_key = "pending-device-secret"
    with app.app_context():
        room = Room(
            room_number="202",
            room_name="Pending Test Room",
            occupancy_status="AVAILABLE",
            is_active=True,
        )
        db.session.add(room)
        db.session.flush()
        db.session.add(
            RoomDevice(
                device_id="PENDING-DEVICE",
                room_id=room.room_id,
                device_code="PENDING-CODE",
                registration_status="PENDING",
                credential_hash=hashlib.sha256(device_key.encode("utf-8")).hexdigest(),
            )
        )
        db.session.commit()
        room_id = room.room_id

    response = unauthenticated_client.post(
        "/api/occupancy/events",
        json={
            "room_id": room_id,
            "device_id": "PENDING-DEVICE",
            "event_type": "MOTION_DETECTED",
            "occupancy_status": "OCCUPIED",
        },
        headers={"X-Device-Key": device_key},
    )
    assert response.status_code == 403
    assert response.json == {"error": "Device is not registered"}


def test_inactive_room_cannot_accept_occupancy_events(app, unauthenticated_client):
    device_key = "inactive-room-device-secret"
    with app.app_context():
        room = Room(
            room_number="203",
            room_name="Deactivated Room",
            occupancy_status="AVAILABLE",
            is_active=False,
        )
        db.session.add(room)
        db.session.flush()
        db.session.add(
            RoomDevice(
                device_id="INACTIVE-ROOM-DEVICE",
                room_id=room.room_id,
                device_code="INACTIVE-ROOM-CODE",
                registration_status="REGISTERED",
                credential_hash=hashlib.sha256(device_key.encode("utf-8")).hexdigest(),
            )
        )
        db.session.commit()
        room_id = room.room_id

    response = unauthenticated_client.post(
        "/api/occupancy/events",
        json={
            "room_id": room_id,
            "device_id": "INACTIVE-ROOM-DEVICE",
            "event_type": "MOTION_DETECTED",
            "occupancy_status": "OCCUPIED",
        },
        headers={"X-Device-Key": device_key},
    )
    assert response.status_code == 403
    assert response.json == {"error": "Room is inactive"}
