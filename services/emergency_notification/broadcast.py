from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.exc import SQLAlchemyError

from database.extensions import db
from database.models.emergency_broadcast import (
    EmergencyBroadcast,
    EmergencyBroadcastTarget,
)
from database.models.room import Room
from services.errors import InvalidReferenceError


def create_broadcast(*, message_text, target_room_ids, created_by):
    unique_room_ids = list(dict.fromkeys(target_room_ids))
    rooms = db.session.query(Room).filter(Room.room_id.in_(unique_room_ids)).all()
    room_map = {room.room_id: room for room in rooms}
    invalid_room_ids = [
        room_id
        for room_id in unique_room_ids
        if room_id not in room_map or not room_map[room_id].is_active
    ]
    if invalid_room_ids:
        raise InvalidReferenceError(
            "One or more target rooms do not exist or are inactive",
            details={"invalid_room_ids": invalid_room_ids},
        )

    try:
        broadcast = EmergencyBroadcast(message_text=message_text, created_by=created_by)
        db.session.add(broadcast)
        db.session.flush()
        broadcast.targets = [
            EmergencyBroadcastTarget(room_id=room_id, delivery_status="PENDING")
            for room_id in unique_room_ids
        ]
        db.session.commit()
        return broadcast
    except SQLAlchemyError:
        db.session.rollback()
        raise


def record_dispatch(*, broadcast_id, room_id):
    """Mark one pending target dispatched without changing terminal states.

    Return the target's current status, or None when the pair was never targeted.
    A repeated report returns DISPATCHED and preserves the original timestamp.
    """
    try:
        result = db.session.execute(
            update(EmergencyBroadcastTarget)
            .where(
                EmergencyBroadcastTarget.broadcast_id == broadcast_id,
                EmergencyBroadcastTarget.room_id == room_id,
                EmergencyBroadcastTarget.delivery_status == "PENDING",
            )
            .values(delivery_status="DISPATCHED", dispatched_at=datetime.now(UTC))
        )
        if result.rowcount:
            db.session.commit()
            return "DISPATCHED"

        return db.session.execute(
            select(EmergencyBroadcastTarget.delivery_status).where(
                EmergencyBroadcastTarget.broadcast_id == broadcast_id,
                EmergencyBroadcastTarget.room_id == room_id,
            )
        ).scalar_one_or_none()
    except SQLAlchemyError:
        db.session.rollback()
        raise


def record_acknowledgment(*, broadcast_id, room_id, allowed_prior_statuses):
    """Acknowledge an existing target using the caller's agreed transition policy.

    The HTTP contract must decide which prior statuses are allowed. Repeated
    acknowledgments never replace the original acknowledgment timestamp.
    Return the target, or None when the broadcast-room pair does not exist.
    """
    allowed_prior_statuses = set(allowed_prior_statuses) - {"ACKNOWLEDGED"}
    try:
        result = db.session.execute(
            update(EmergencyBroadcastTarget)
            .where(
                EmergencyBroadcastTarget.broadcast_id == broadcast_id,
                EmergencyBroadcastTarget.room_id == room_id,
                EmergencyBroadcastTarget.delivery_status.in_(allowed_prior_statuses),
            )
            .values(delivery_status="ACKNOWLEDGED", acknowledged_at=datetime.now(UTC))
        )
        if result.rowcount:
            db.session.commit()

        return db.session.execute(
            select(EmergencyBroadcastTarget).where(
                EmergencyBroadcastTarget.broadcast_id == broadcast_id,
                EmergencyBroadcastTarget.room_id == room_id,
            )
        ).scalar_one_or_none()
    except SQLAlchemyError:
        db.session.rollback()
        raise
