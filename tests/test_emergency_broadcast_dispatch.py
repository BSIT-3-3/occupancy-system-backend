from database.extensions import db
from database.models.emergency_broadcast import EmergencyBroadcastTarget
from database.models.room import Room
from services.emergency_notification.broadcast import record_dispatch

ROUTE = "/api/admin/emergency-broadcasts"


def _create_broadcast(client, room_ids):
    response = client.post(
        ROUTE, json={"message_text": "Evacuate now", "target_room_ids": room_ids}
    )
    assert response.status_code == 201
    return response.json["broadcast_id"]


def test_dispatch_changes_only_one_broadcast_room_pair_and_is_repeatable(app, client):
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
        first_target = (
            db.session.query(EmergencyBroadcastTarget)
            .filter_by(broadcast_id=first_broadcast_id, room_id=room_ids[0])
            .one()
        )
        first_dispatched_at = first_target.dispatched_at
        assert first_dispatched_at is not None
        assert (
            record_dispatch(broadcast_id=first_broadcast_id, room_id=room_ids[0])
            == "DISPATCHED"
        )
        db.session.refresh(first_target)
        assert first_target.dispatched_at == first_dispatched_at

        other_room = (
            db.session.query(EmergencyBroadcastTarget)
            .filter_by(broadcast_id=first_broadcast_id, room_id=room_ids[1])
            .one()
        )
        other_broadcast = (
            db.session.query(EmergencyBroadcastTarget)
            .filter_by(broadcast_id=second_broadcast_id, room_id=room_ids[0])
            .one()
        )
        assert other_room.delivery_status == "PENDING"
        assert other_broadcast.delivery_status == "PENDING"
        assert record_dispatch(broadcast_id=second_broadcast_id, room_id=999) is None
        assert db.session.query(EmergencyBroadcastTarget).count() == 3


def test_late_dispatch_does_not_overwrite_terminal_status(app, client):
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
        targets = (
            db.session.query(EmergencyBroadcastTarget)
            .filter_by(broadcast_id=broadcast_id)
            .all()
        )
        by_room = {target.room_id: target for target in targets}
        by_room[room_ids[0]].delivery_status = "ACKNOWLEDGED"
        by_room[room_ids[1]].delivery_status = "FAILED"
        db.session.commit()

        assert (
            record_dispatch(broadcast_id=broadcast_id, room_id=room_ids[0])
            == "ACKNOWLEDGED"
        )
        assert (
            record_dispatch(broadcast_id=broadcast_id, room_id=room_ids[1]) == "FAILED"
        )
        db.session.refresh(by_room[room_ids[0]])
        db.session.refresh(by_room[room_ids[1]])
        assert by_room[room_ids[0]].dispatched_at is None
        assert by_room[room_ids[1]].dispatched_at is None
