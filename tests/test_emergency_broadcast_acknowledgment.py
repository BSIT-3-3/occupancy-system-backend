from database.extensions import db
from database.models.emergency_broadcast import EmergencyBroadcastTarget
from database.models.room import Room
from services.emergency_notification.broadcast import (
    record_acknowledgment,
    record_dispatch,
)

ROUTE = "/api/admin/emergency-broadcasts"


def _create_broadcast(client, room_ids):
    response = client.post(
        ROUTE, json={"message_text": "Evacuate now", "target_room_ids": room_ids}
    )
    assert response.status_code == 201
    return response.json["broadcast_id"]


def test_acknowledgment_updates_only_one_pair_and_preserves_timestamp(app, client):
    with app.app_context():
        rooms = [
            Room(room_number="101", room_name="Room 101"),
            Room(room_number="102", room_name="Room 102"),
        ]
        db.session.add_all(rooms)
        db.session.commit()
        room_ids = [room.room_id for room in rooms]

    first_broadcast_id = _create_broadcast(client, room_ids)
    second_broadcast_id = _create_broadcast(client, [room_ids[0]])

    with app.app_context():
        assert (
            record_dispatch(broadcast_id=first_broadcast_id, room_id=room_ids[0])
            == "DISPATCHED"
        )
        acknowledged = record_acknowledgment(
            broadcast_id=first_broadcast_id,
            room_id=room_ids[0],
            allowed_prior_statuses={"DISPATCHED"},
        )
        assert acknowledged.delivery_status == "ACKNOWLEDGED"
        original_acknowledged_at = acknowledged.acknowledged_at
        assert original_acknowledged_at is not None

        repeated = record_acknowledgment(
            broadcast_id=first_broadcast_id,
            room_id=room_ids[0],
            allowed_prior_statuses={"DISPATCHED"},
        )
        assert repeated.acknowledged_at == original_acknowledged_at
        assert (
            record_dispatch(broadcast_id=first_broadcast_id, room_id=room_ids[0])
            == "ACKNOWLEDGED"
        )

        db.session.expire_all()
        statuses = {
            (target.broadcast_id, target.room_id): target.delivery_status
            for target in db.session.query(EmergencyBroadcastTarget).all()
        }
        assert statuses == {
            (first_broadcast_id, room_ids[0]): "ACKNOWLEDGED",
            (first_broadcast_id, room_ids[1]): "PENDING",
            (second_broadcast_id, room_ids[0]): "PENDING",
        }
        assert db.session.query(EmergencyBroadcastTarget).count() == 3


def test_acknowledgment_policy_and_unknown_pair_leave_records_unchanged(app, client):
    with app.app_context():
        rooms = [
            Room(room_number="101", room_name="Room 101"),
            Room(room_number="102", room_name="Room 102"),
        ]
        db.session.add_all(rooms)
        db.session.commit()
        room_ids = [room.room_id for room in rooms]

    broadcast_id = _create_broadcast(client, room_ids)
    with app.app_context():
        failed = (
            db.session.query(EmergencyBroadcastTarget)
            .filter_by(broadcast_id=broadcast_id, room_id=room_ids[1])
            .one()
        )
        failed.delivery_status = "FAILED"
        db.session.commit()

        pending = record_acknowledgment(
            broadcast_id=broadcast_id,
            room_id=room_ids[0],
            allowed_prior_statuses={"DISPATCHED"},
        )
        still_failed = record_acknowledgment(
            broadcast_id=broadcast_id,
            room_id=room_ids[1],
            allowed_prior_statuses={"DISPATCHED"},
        )
        missing_room = record_acknowledgment(
            broadcast_id=broadcast_id,
            room_id=999,
            allowed_prior_statuses={"DISPATCHED"},
        )
        missing_broadcast = record_acknowledgment(
            broadcast_id=999,
            room_id=room_ids[0],
            allowed_prior_statuses={"DISPATCHED"},
        )
        assert pending.delivery_status == "PENDING"
        assert pending.acknowledged_at is None
        assert still_failed.delivery_status == "FAILED"
        assert still_failed.acknowledged_at is None
        assert missing_room is None
        assert missing_broadcast is None
        assert db.session.query(EmergencyBroadcastTarget).count() == 2
