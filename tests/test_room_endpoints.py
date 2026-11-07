from database.extensions import db
from database.models.assistance_request import AssistanceRequest
from database.models.occupancy_event import OccupancyEvent
from database.models.room import Room
from database.models.room_device import RoomDevice


def _room_payload(room_number="101", room_name="Room 101"):
    return {"room_number": room_number, "room_name": room_name}


def test_room_api_supports_the_seven_monitored_rooms(client):
    first_room_id = None
    for number in range(101, 108):
        response = client.post(
            "/rooms", json=_room_payload(str(number), f"Room {number}")
        )
        assert response.status_code == 201
        if first_room_id is None:
            first_room_id = response.json["room_id"]
        assert response.json["room_number"] == str(number)
        assert response.json["occupancy_status"] == "AVAILABLE"
        assert response.json["is_active"] is True
        assert response.json["last_occupancy_update"] is None

    listed = client.get("/rooms")
    assert listed.status_code == 200
    assert [room["room_number"] for room in listed.json] == [
        str(number) for number in range(101, 108)
    ]
    first_room = client.get(f"/rooms/{first_room_id}")
    assert first_room.status_code == 200
    assert first_room.json["room_number"] == "101"


def test_get_room_by_id_returns_404_for_unknown_room(client):
    missing = client.get("/rooms/999")
    assert missing.status_code == 404
    assert missing.json == {"error": "Room not found"}


def test_room_update_supports_put_and_patch(client):
    created = client.post("/rooms", json=_room_payload())
    room_id = created.json["room_id"]

    replaced = client.put(
        f"/rooms/{room_id}",
        json={"room_number": "102", "room_name": "Lecture Room"},
    )
    assert replaced.status_code == 200
    assert replaced.json["room_number"] == "102"
    assert replaced.json["room_name"] == "Lecture Room"

    patched = client.patch(f"/rooms/{room_id}", json={"room_name": "Lecture Hall"})
    assert patched.status_code == 200
    assert patched.json["room_number"] == "102"
    assert patched.json["room_name"] == "Lecture Hall"

    deactivated = client.patch(f"/rooms/{room_id}", json={"is_active": False})
    assert deactivated.status_code == 200
    assert deactivated.json["is_active"] is False


def test_room_delete_deactivates_and_preserves_related_history(client, app):
    created = client.post("/rooms", json=_room_payload())
    room_id = created.json["room_id"]

    with app.app_context():
        db.session.add(
            RoomDevice(
                device_id="ROOM-101",
                room_id=room_id,
                device_code="SENSOR-101",
                registration_status="REGISTERED",
            )
        )
        db.session.flush()
        db.session.add(
            OccupancyEvent(
                room_id=room_id,
                device_id="ROOM-101",
                event_type="MOTION_DETECTED",
                occupancy_status="OCCUPIED",
            )
        )
        db.session.add(
            AssistanceRequest(
                room_id=room_id,
                device_id="ROOM-101",
                status="PENDING",
            )
        )
        db.session.commit()

    deleted = client.delete(f"/rooms/{room_id}")
    assert deleted.status_code == 200
    assert deleted.json == {"message": "Room deactivated", "room_id": room_id}

    with app.app_context():
        room = db.session.get(Room, room_id)
        assert room is not None
        assert room.is_active is False
        assert db.session.query(OccupancyEvent).filter_by(room_id=room_id).count() == 1
        assert (
            db.session.query(AssistanceRequest).filter_by(room_id=room_id).count()
            == 1
        )

    listed = client.get("/rooms")
    assert listed.json[0]["is_active"] is False


def test_room_number_must_be_unique_and_sensor_fields_are_read_only(client):
    assert client.post("/rooms", json=_room_payload()).status_code == 201
    duplicate = client.post("/rooms", json=_room_payload("101", "Another Room"))
    assert duplicate.status_code == 409

    status_update = client.patch(
        "/rooms/1", json={"occupancy_status": "OCCUPIED"}
    )
    assert status_update.status_code == 400
    assert status_update.json["error"] == "Unsupported fields"


def test_room_payload_validation_and_authentication(client, unauthenticated_client):
    assert client.post("/rooms", json=[]).status_code == 400
    assert client.post("/rooms", json={"room_number": "101"}).status_code == 400
    assert (
        client.post("/rooms", json={**_room_payload(), "is_active": "false"}).status_code
        == 400
    )
    assert unauthenticated_client.get("/rooms").status_code == 401


def test_inactive_room_rejects_new_assistance_requests(app, unauthenticated_client):
    with app.app_context():
        room = Room(
            room_number="105",
            room_name="Inactive Room",
            is_active=False,
        )
        db.session.add(room)
        db.session.flush()
        db.session.add(
            RoomDevice(
                device_id="INACTIVE-DEVICE",
                room_id=room.room_id,
                device_code="INACTIVE-CODE",
                registration_status="REGISTERED",
            )
        )
        db.session.commit()
        room_id = room.room_id

    response = unauthenticated_client.post(
        "/assistance-requests",
        json={"room_id": room_id, "device_id": "INACTIVE-DEVICE"},
    )
    assert response.status_code == 403
    assert response.json == {"error": "Room is inactive"}



def test_deactivating_a_room_deactivates_its_assigned_device(client, app):
    created = client.post("/rooms", json=_room_payload())
    room_id = created.json["room_id"]
    registered = client.post(
        "/devices",
        json={
            "device_id": "DEV001",
            "device_code": "ESP32-001",
            "room_id": room_id,
            "device_name": "Room Sensor",
        },
    )
    assert registered.status_code == 201

    deleted = client.delete(f"/rooms/{room_id}")
    assert deleted.status_code == 200

    with app.app_context():
        room = db.session.get(Room, room_id)
        assert room.is_active is False
        device = db.session.get(RoomDevice, "DEV001")
        # The device record is preserved (not deleted) and its room link is
        # kept, but it is deactivated so it cannot remain actively assigned
        # to an inactive room.
        assert device is not None
        assert device.room_id == room_id
        assert device.registration_status == "DEACTIVATED"


def test_patching_room_inactive_deactivates_its_assigned_device(client, app):
    created = client.post("/rooms", json=_room_payload("201", "Room 201"))
    room_id = created.json["room_id"]
    registered = client.post(
        "/devices",
        json={
            "device_id": "DEV201",
            "device_code": "ESP32-201",
            "room_id": room_id,
        },
    )
    assert registered.status_code == 201

    patched = client.patch(f"/rooms/{room_id}", json={"is_active": False})
    assert patched.status_code == 200

    with app.app_context():
        device = db.session.get(RoomDevice, "DEV201")
        assert device is not None
        assert device.room_id == room_id
        assert device.registration_status == "DEACTIVATED"
