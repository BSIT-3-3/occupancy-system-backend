import hashlib

from database.extensions import db
from database.models.emergency_broadcast import EmergencyBroadcastTarget
from database.models.room import Room
from database.models.room_device import RoomDevice
from services.emergency_notification.broadcast import record_dispatch

CREATE_ROUTE = "/api/admin/emergency-broadcasts"
KEYS = {"DEVICE-101": "room-101-test-key", "DEVICE-102": "room-102-test-key"}


def _seed_devices(app):
    with app.app_context():
        rooms = [
            Room(room_number="101", room_name="Room 101"),
            Room(room_number="102", room_name="Room 102"),
        ]
        db.session.add_all(rooms)
        db.session.flush()
        for room, device_id in zip(rooms, KEYS, strict=True):
            db.session.add(
                RoomDevice(
                    device_id=device_id,
                    room_id=room.room_id,
                    device_code=device_id,
                    registration_status="REGISTERED",
                    credential_hash=hashlib.sha256(
                        KEYS[device_id].encode("utf-8")
                    ).hexdigest(),
                )
            )
        db.session.commit()
        return [room.room_id for room in rooms]


def _create(client, room_ids):
    response = client.post(
        CREATE_ROUTE,
        json={"message_text": "Evacuate now", "target_room_ids": room_ids},
    )
    assert response.status_code == 201
    return response.json["broadcast_id"]


def _ack(client, broadcast_id, device_id="DEVICE-101", key=None, **kwargs):
    return client.post(
        f"/api/gateway/emergency-broadcasts/{broadcast_id}/acknowledgments",
        json={"device_id": device_id, **kwargs},
        headers={"X-Device-Key": KEYS[device_id] if key is None else key},
    )


def test_pending_acknowledgment_is_scoped_repeatable_and_survives_late_dispatch(
    app, client, unauthenticated_client
):
    room_ids = _seed_devices(app)
    first_broadcast = _create(client, room_ids)
    second_broadcast = _create(client, [room_ids[0]])

    first = _ack(unauthenticated_client, first_broadcast)
    assert first.status_code == 200
    assert first.json["broadcast_id"] == first_broadcast
    assert first.json["room_id"] == room_ids[0]
    assert first.json["device_id"] == "DEVICE-101"
    assert first.json["delivery_status"] == "ACKNOWLEDGED"
    assert first.json["acknowledged_at"]

    repeated = _ack(unauthenticated_client, first_broadcast)
    assert repeated.status_code == 200
    assert repeated.json == first.json

    with app.app_context():
        assert (
            record_dispatch(broadcast_id=first_broadcast, room_id=room_ids[0])
            == "ACKNOWLEDGED"
        )
        db.session.expire_all()
        statuses = {
            (target.broadcast_id, target.room_id): target.delivery_status
            for target in db.session.query(EmergencyBroadcastTarget).all()
        }
        assert statuses == {
            (first_broadcast, room_ids[0]): "ACKNOWLEDGED",
            (first_broadcast, room_ids[1]): "PENDING",
            (second_broadcast, room_ids[0]): "PENDING",
        }
        assert db.session.query(EmergencyBroadcastTarget).count() == 3


def test_dispatched_target_can_be_acknowledged(app, client, unauthenticated_client):
    room_ids = _seed_devices(app)
    broadcast_id = _create(client, [room_ids[0]])
    with app.app_context():
        assert record_dispatch(broadcast_id=broadcast_id, room_id=room_ids[0]) == (
            "DISPATCHED"
        )

    response = _ack(unauthenticated_client, broadcast_id)
    assert response.status_code == 200
    assert response.json["delivery_status"] == "ACKNOWLEDGED"
    with app.app_context():
        target = db.session.query(EmergencyBroadcastTarget).one()
        assert target.dispatched_at is not None
        assert target.acknowledged_at is not None


def test_failed_target_rejects_acknowledgment(app, client, unauthenticated_client):
    room_ids = _seed_devices(app)
    broadcast_id = _create(client, [room_ids[0]])
    with app.app_context():
        target = db.session.query(EmergencyBroadcastTarget).one()
        target.delivery_status = "FAILED"
        db.session.commit()

    response = _ack(unauthenticated_client, broadcast_id)
    assert response.status_code == 409
    assert response.json == {"error": "Broadcast target has failed"}
    with app.app_context():
        target = db.session.query(EmergencyBroadcastTarget).one()
        assert target.delivery_status == "FAILED"
        assert target.acknowledged_at is None


def test_unknown_broadcast_and_untargeted_room_do_not_create_targets(
    app, client, unauthenticated_client
):
    room_ids = _seed_devices(app)
    broadcast_id = _create(client, [room_ids[0]])

    unknown = _ack(unauthenticated_client, 999)
    untargeted = _ack(unauthenticated_client, broadcast_id, device_id="DEVICE-102")
    assert unknown.status_code == 404
    assert unknown.json == {"error": "Emergency broadcast not found"}
    assert untargeted.status_code == 404
    assert untargeted.json == {"error": "Broadcast target not found"}
    with app.app_context():
        targets = db.session.query(EmergencyBroadcastTarget).all()
        assert len(targets) == 1
        assert targets[0].room_id == room_ids[0]
        assert targets[0].delivery_status == "PENDING"


def test_invalid_credentials_and_device_identity_cannot_acknowledge(
    app, client, unauthenticated_client
):
    room_ids = _seed_devices(app)
    broadcast_id = _create(client, [room_ids[0]])
    url = f"/api/gateway/emergency-broadcasts/{broadcast_id}/acknowledgments"

    missing = unauthenticated_client.post(url, json={"device_id": "DEVICE-101"})
    wrong = _ack(unauthenticated_client, broadcast_id, key="wrong-key")
    other_device_key = unauthenticated_client.post(
        url,
        json={"device_id": "DEVICE-102"},
        headers={"X-Device-Key": KEYS["DEVICE-101"]},
    )
    admin_token_only = client.post(url, json={"device_id": "DEVICE-101"})
    for response in (missing, wrong, other_device_key, admin_token_only):
        assert response.status_code == 401
        assert response.json == {"error": "Invalid device credentials"}

    with app.app_context():
        db.session.get(RoomDevice, "DEVICE-101").registration_status = "PENDING"
        db.session.commit()
    unregistered = _ack(unauthenticated_client, broadcast_id)
    assert unregistered.status_code == 403
    assert unregistered.json == {"error": "Device is not registered"}
    with app.app_context():
        assert db.session.query(EmergencyBroadcastTarget).one().delivery_status == (
            "PENDING"
        )


def test_malformed_acknowledgments_leave_status_unchanged(
    app, client, unauthenticated_client
):
    room_ids = _seed_devices(app)
    broadcast_id = _create(client, [room_ids[0]])
    url = f"/api/gateway/emergency-broadcasts/{broadcast_id}/acknowledgments"
    headers = {"X-Device-Key": KEYS["DEVICE-101"]}
    requests = [
        {"data": "not-json"},
        {"json": []},
        {"json": {}},
        {"json": {"device_id": ""}},
        {"json": {"device_id": 12}},
        {"json": {"device_id": "DEVICE-101", "room_id": room_ids[1]}},
    ]
    for request_args in requests:
        response = unauthenticated_client.post(url, headers=headers, **request_args)
        assert response.status_code == 400

    with app.app_context():
        target = db.session.query(EmergencyBroadcastTarget).one()
        assert target.delivery_status == "PENDING"
        assert target.acknowledged_at is None
