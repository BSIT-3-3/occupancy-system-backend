from database.extensions import db
from database.models.occupancy_event import OccupancyEvent
from database.models.room_device import RoomDevice


def _create_room(client, room_number="101", room_name="Room 101"):
    response = client.post(
        "/rooms", json={"room_number": room_number, "room_name": room_name}
    )
    assert response.status_code == 201, response.json
    return response.json["room_id"]


def _device_payload(device_id="DEV001", device_code="ESP32-001", room_id=1,
                    device_name="Room Sensor"):
    return {
        "device_id": device_id,
        "device_code": device_code,
        "room_id": room_id,
        "device_name": device_name,
    }


def test_device_registration_and_retrieval(client):
    room_id = _create_room(client)

    created = client.post("/devices", json=_device_payload(room_id=room_id))
    assert created.status_code == 201, created.json
    body = created.json
    assert body["device_id"] == "DEV001"
    assert body["device_code"] == "ESP32-001"
    assert body["device_name"] == "Room Sensor"
    assert body["room_id"] == room_id
    assert body["registration_status"] == "PENDING"
    assert "registered_at" in body
    # The credential hash must never be exposed by the management API.
    assert "credential_hash" not in body
    assert body["room"] == {
        "room_id": room_id,
        "room_number": "101",
        "room_name": "Room 101",
        "is_active": True,
    }

    listed = client.get("/devices")
    assert listed.status_code == 200
    assert [device["device_id"] for device in listed.json] == ["DEV001"]

    one = client.get("/devices/DEV001")
    assert one.status_code == 200
    assert one.json["device_code"] == "ESP32-001"


def test_get_device_returns_404_for_unknown_device(client):
    missing = client.get("/devices/NOPE")
    assert missing.status_code == 404
    assert missing.json == {"error": "Device not found"}


def test_device_update_supports_put_patch_and_reactivation(client):
    room_id = _create_room(client)
    client.post("/devices", json=_device_payload(room_id=room_id))

    replaced = client.put(
        "/devices/DEV001",
        json={
            "device_code": "ESP32-1A",
            "room_id": room_id,
            "device_name": "Renamed Sensor",
        },
    )
    assert replaced.status_code == 200, replaced.json
    assert replaced.json["device_code"] == "ESP32-1A"
    assert replaced.json["device_name"] == "Renamed Sensor"

    patched = client.patch("/devices/DEV001", json={"device_name": "Lab Sensor"})
    assert patched.status_code == 200
    assert patched.json["device_name"] == "Lab Sensor"
    assert patched.json["device_code"] == "ESP32-1A"

    deactivated = client.patch(
        "/devices/DEV001", json={"registration_status": "DEACTIVATED"}
    )
    assert deactivated.status_code == 200
    assert deactivated.json["registration_status"] == "DEACTIVATED"

    reactivated = client.patch(
        "/devices/DEV001", json={"registration_status": "pending"}
    )
    assert reactivated.status_code == 200
    assert reactivated.json["registration_status"] == "PENDING"


def test_room_reassignment_keeps_one_device_per_room(client):
    room_a = _create_room(client, "101", "Room 101")
    room_b = _create_room(client, "102", "Room 102")

    created = client.post("/devices", json=_device_payload(room_id=room_a))
    assert created.status_code == 201

    moved = client.patch("/devices/DEV001", json={"room_id": room_b})
    assert moved.status_code == 200, moved.json
    assert moved.json["room_id"] == room_b
    assert moved.json["room"]["room_number"] == "102"

    # Room 101 is now free, so a second device can take it.
    second = client.post(
        "/devices",
        json=_device_payload("DEV002", "ESP32-002", room_id=room_a, device_name="Second"),
    )
    assert second.status_code == 201

    # Room 102 already holds DEV001, so reassigning DEV002 there must fail.
    conflict = client.patch("/devices/DEV002", json={"room_id": room_b})
    assert conflict.status_code == 409
    assert conflict.json["error"] == "Room already has a device assigned"


def test_assigning_to_inactive_room_returns_409(client):
    room_id = _create_room(client)
    deactivated = client.delete(f"/rooms/{room_id}")
    assert deactivated.status_code == 200

    response = client.post("/devices", json=_device_payload(room_id=room_id))
    assert response.status_code == 409
    assert response.json["error"] == "Room is inactive"

    # Reassigning an existing device to an inactive room is also rejected.
    active_room = _create_room(client, "102", "Room 102")
    client.post(
        "/devices",
        json=_device_payload("DEV010", "ESP32-010", room_id=active_room, device_name="Sensor"),
    )
    reassign = client.patch("/devices/DEV010", json={"room_id": room_id})
    assert reassign.status_code == 409
    assert reassign.json["error"] == "Room is inactive"


def test_duplicate_device_id_and_code_are_rejected(client):
    room_id = _create_room(client)
    assert client.post("/devices", json=_device_payload(room_id=room_id)).status_code == 201

    same_id = client.post(
        "/devices",
        json=_device_payload("DEV001", "ESP32-999", room_id=room_id, device_name="Other"),
    )
    assert same_id.status_code == 409
    assert same_id.json["error"] == "Device ID already exists"

    same_code = client.post(
        "/devices",
        json=_device_payload("DEV002", "ESP32-001", room_id=room_id, device_name="Other"),
    )
    assert same_code.status_code == 409
    assert same_code.json["error"] == "Device code already exists"


def test_device_deactivation_preserves_history(client, app):
    room_id = _create_room(client)
    created = client.post("/devices", json=_device_payload(room_id=room_id))
    device_id = created.json["device_id"]

    with app.app_context():
        db.session.add(
            OccupancyEvent(
                room_id=room_id,
                device_id=device_id,
                event_type="MOTION_DETECTED",
                occupancy_status="OCCUPIED",
            )
        )
        db.session.commit()

    deleted = client.delete(f"/devices/{device_id}")
    assert deleted.status_code == 200
    assert deleted.json == {"message": "Device deactivated", "device_id": device_id}

    with app.app_context():
        device = db.session.get(RoomDevice, device_id)
        assert device is not None
        assert device.registration_status == "DEACTIVATED"
        assert (
            db.session.query(OccupancyEvent).filter_by(device_id=device_id).count() == 1
        )

    fetched = client.get(f"/devices/{device_id}")
    assert fetched.status_code == 200
    assert fetched.json["registration_status"] == "DEACTIVATED"


def test_one_device_per_monitored_room_for_all_seven_rooms(client):
    room_ids = {}
    for number in range(101, 108):
        room_ids[number] = _create_room(client, str(number), f"Room {number}")

    for index, number in enumerate(range(101, 108), start=1):
        device_id = f"DEV{index:03d}"
        device_code = f"ESP32-{index:03d}"
        response = client.post(
            "/devices",
            json=_device_payload(device_id, device_code, room_id=room_ids[number]),
        )
        assert response.status_code == 201

    listed = client.get("/devices")
    assert listed.status_code == 200
    assert [device["device_id"] for device in listed.json] == [
        f"DEV{index:03d}" for index in range(1, 8)
    ]

    # An eighth device cannot reuse an already-assigned room.
    extra = client.post(
        "/devices",
        json=_device_payload("DEV008", "ESP32-008", room_id=room_ids[101]),
    )
    assert extra.status_code == 409
    assert extra.json["error"] == "Room already has a device assigned"


def test_device_payload_validation_and_authentication(client, unauthenticated_client):
    room_id = _create_room(client)

    assert client.post("/devices", json=[]).status_code == 400
    assert client.post(
        "/devices",
        json={"device_id": "DEV001", "device_code": "ESP32-001"},
    ).status_code == 400
    assert client.post(
        "/devices",
        json={
            "device_id": "DEV001",
            "device_code": "ESP32-001",
            "room_id": "not-an-integer",
        },
    ).status_code == 400

    unsupported = client.post(
        "/devices",
        json={
            "device_id": "DEV001",
            "device_code": "ESP32-001",
            "room_id": room_id,
            "credential_hash": "should-be-rejected",
        },
    )
    assert unsupported.status_code == 400
    assert unsupported.json["error"] == "Unsupported fields"

    # device_id is the primary key and must stay read-only after creation.
    client.post("/devices", json=_device_payload(room_id=room_id))
    immutable = client.patch("/devices/DEV001", json={"device_id": "DEV999"})
    assert immutable.status_code == 400
    assert immutable.json["error"] == "Unsupported fields"

    # Activation to REGISTERED is owned by the device-key CLI, not management.
    bad_status = client.patch(
        "/devices/DEV001", json={"registration_status": "REGISTERED"}
    )
    assert bad_status.status_code == 400
    assert bad_status.json["error"] == "Invalid registration_status"

    assert unauthenticated_client.get("/devices").status_code == 401



def test_available_rooms_returns_only_active_unassigned_rooms(client):
    room_assigned = _create_room(client, "101", "Assigned")
    room_free = _create_room(client, "102", "Free")
    room_inactive = _create_room(client, "103", "Inactive")

    client.post(
        "/devices",
        json=_device_payload("DEV001", "ESP32-001", room_id=room_assigned),
    )
    client.delete(f"/rooms/{room_inactive}")

    response = client.get("/devices/available-rooms")
    assert response.status_code == 200
    rooms = response.json
    assert [room["room_number"] for room in rooms] == ["102"]
    assert all(room["is_active"] is True for room in rooms)


def test_releasing_a_room_makes_it_available_again(client):
    room_a = _create_room(client, "101", "Room A")
    room_b = _create_room(client, "102", "Room B")
    client.post(
        "/devices", json=_device_payload("DEV001", "ESP32-001", room_id=room_a)
    )

    # Moving the device out of room A makes A available again.
    moved = client.patch("/devices/DEV001", json={"room_id": room_b})
    assert moved.status_code == 200

    response = client.get("/devices/available-rooms")
    assert response.status_code == 200
    assert [room["room_number"] for room in response.json] == ["101"]


def test_available_rooms_requires_admin(unauthenticated_client):
    assert (
        unauthenticated_client.get("/devices/available-rooms").status_code == 401
    )
