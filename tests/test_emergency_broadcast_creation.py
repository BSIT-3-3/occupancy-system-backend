from datetime import UTC, datetime, timedelta

import pytest
from flask_jwt_extended import create_access_token
from sqlalchemy import event
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from database.extensions import db
from database.models.emergency_broadcast import (
    EmergencyBroadcast,
    EmergencyBroadcastTarget,
)
from database.models.role import Role
from database.models.room import Room
from database.models.user import User
from database.models.user_session import UserSession

ROUTE = "/api/admin/emergency-broadcasts"


def _add_rooms():
    rooms = [
        Room(room_number="101", room_name="Room 101"),
        Room(room_number="102", room_name="Room 102"),
    ]
    db.session.add_all(rooms)
    db.session.commit()
    return [room.room_id for room in rooms]


def test_admin_creates_broadcast_with_two_pending_targets(app, client):
    with app.app_context():
        room_ids = _add_rooms()

    response = client.post(
        ROUTE,
        json={"message_text": "  Evacuate now  ", "target_room_ids": room_ids},
        headers={"X-Admin-User-ID": "999"},
    )

    assert response.status_code == 201
    broadcast_id = response.json["broadcast_id"]
    assert response.json["message_text"] == "Evacuate now"
    assert [target["room_id"] for target in response.json["targets"]] == room_ids
    assert [target["delivery_status"] for target in response.json["targets"]] == [
        "PENDING",
        "PENDING",
    ]

    with app.app_context():
        broadcast = db.session.get(EmergencyBroadcast, broadcast_id)
        assert broadcast.message_text == "Evacuate now"
        assert broadcast.created_by == app.config["TEST_ADMIN_ID"]
        targets = (
            db.session.query(EmergencyBroadcastTarget)
            .filter_by(broadcast_id=broadcast_id)
            .all()
        )
        assert len(targets) == 2
        assert {target.room_id for target in targets} == set(room_ids)
        assert {target.delivery_status for target in targets} == {"PENDING"}


def test_non_admin_and_unauthenticated_callers_cannot_create(
    app, unauthenticated_client
):
    with app.app_context():
        room_ids = _add_rooms()
        staff_role = Role(role_name="STAFF", description="Staff")
        db.session.add(staff_role)
        db.session.flush()
        staff = User(
            username="staff-broadcast",
            password="test-only-password-hash",
            role_id=staff_role.role_id,
            status="ACTIVE",
        )
        db.session.add(staff)
        db.session.flush()
        session = UserSession(
            user_id=staff.user_id,
            expires_at=datetime.now(UTC) + timedelta(days=1),
        )
        db.session.add(session)
        db.session.flush()
        token = create_access_token(
            identity=str(staff.user_id), additional_claims={"sid": session.session_id}
        )
        db.session.commit()

    payload = {"message_text": "Evacuate now", "target_room_ids": room_ids}
    missing = unauthenticated_client.post(ROUTE, json=payload)
    non_admin = unauthenticated_client.post(
        ROUTE, json=payload, headers={"Authorization": f"Bearer {token}"}
    )
    assert missing.status_code == 401
    assert missing.json == {"error": "Authentication required"}
    assert non_admin.status_code == 403
    assert non_admin.json == {"error": "Admin access required"}

    with app.app_context():
        assert db.session.query(EmergencyBroadcast).count() == 0
        assert db.session.query(EmergencyBroadcastTarget).count() == 0


@pytest.mark.parametrize(
    "payload",
    [
        {"message_text": "  ", "target_room_ids": [1]},
        {"message_text": "Alert", "target_room_ids": []},
        {"message_text": "Alert", "target_room_ids": "1"},
        {"message_text": "Alert", "target_room_ids": [True]},
        {"message_text": "Alert", "target_room_ids": [1, 999]},
    ],
)
def test_invalid_creation_does_not_persist_partial_records(app, client, payload):
    with app.app_context():
        _add_rooms()

    response = client.post(ROUTE, json=payload)
    assert response.status_code == 400

    with app.app_context():
        assert db.session.query(EmergencyBroadcast).count() == 0
        assert db.session.query(EmergencyBroadcastTarget).count() == 0


def test_database_rejects_duplicate_targets_and_invalid_status(app, client):
    with app.app_context():
        room_ids = _add_rooms()
    created = client.post(
        ROUTE, json={"message_text": "Alert", "target_room_ids": room_ids}
    )
    assert created.status_code == 201

    with app.app_context():
        db.session.add(
            EmergencyBroadcastTarget(
                broadcast_id=created.json["broadcast_id"], room_id=room_ids[0]
            )
        )
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()

        target = (
            db.session.query(EmergencyBroadcastTarget)
            .filter_by(broadcast_id=created.json["broadcast_id"], room_id=room_ids[0])
            .one()
        )
        target.delivery_status = "INVALID"
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()
        assert db.session.query(EmergencyBroadcastTarget).count() == 2


def test_target_insert_failure_rolls_back_broadcast(app, client):
    with app.app_context():
        room_ids = _add_rooms()

    def fail_target_insert(_mapper, _connection, _target):
        raise SQLAlchemyError("simulated target insert failure")

    event.listen(EmergencyBroadcastTarget, "before_insert", fail_target_insert)
    try:
        response = client.post(
            ROUTE, json={"message_text": "Alert", "target_room_ids": room_ids}
        )
    finally:
        event.remove(EmergencyBroadcastTarget, "before_insert", fail_target_insert)

    assert response.status_code == 500
    assert response.json == {"error": "Database operation failed"}
    with app.app_context():
        assert db.session.query(EmergencyBroadcast).count() == 0
        assert db.session.query(EmergencyBroadcastTarget).count() == 0


def test_duplicate_room_ids_are_saved_once_without_device_or_occupancy_rule(
    app, client
):
    with app.app_context():
        room_ids = _add_rooms()
        room = db.session.get(Room, room_ids[0])
        room.occupancy_status = "OCCUPIED"
        db.session.commit()

    response = client.post(
        ROUTE,
        json={"message_text": "Alert", "target_room_ids": [room_ids[0], *room_ids]},
    )
    assert response.status_code == 201
    assert [target["room_id"] for target in response.json["targets"]] == room_ids
    with app.app_context():
        assert db.session.query(EmergencyBroadcastTarget).count() == 2


def test_inactive_room_is_rejected_without_partial_records(app, client):
    with app.app_context():
        room_ids = _add_rooms()
        db.session.get(Room, room_ids[1]).is_active = False
        db.session.commit()

    response = client.post(
        ROUTE, json={"message_text": "Alert", "target_room_ids": room_ids}
    )
    assert response.status_code == 400
    assert response.json["invalid_room_ids"] == [room_ids[1]]
    with app.app_context():
        assert db.session.query(EmergencyBroadcast).count() == 0
        assert db.session.query(EmergencyBroadcastTarget).count() == 0
