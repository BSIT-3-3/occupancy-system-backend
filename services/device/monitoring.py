from datetime import UTC, datetime, timedelta

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import joinedload

from database.extensions import db
from database.models.device_status_log import DeviceStatusLog
from database.models.room import Room
from database.models.room_device import RoomDevice


def reconcile_offline_devices(timeout_seconds, *, now=None):
    """Mark registered devices offline after their last heartbeat expires."""
    now = now or datetime.now(UTC)
    cutoff = now - timedelta(seconds=timeout_seconds)
    changed = 0
    try:
        devices = (
            db.session.query(RoomDevice)
            .filter(
                RoomDevice.current_status == "ONLINE",
                RoomDevice.last_communication_at.is_not(None),
                RoomDevice.last_communication_at <= cutoff,
                RoomDevice.registration_status == "REGISTERED",
            )
            .with_for_update()
            .all()
        )
        for device in devices:
            if device.room is None or not device.room.is_active:
                continue
            device.current_status = "OFFLINE"
            db.session.add(
                DeviceStatusLog(
                    device_id=device.device_id,
                    previous_status="ONLINE",
                    new_status="OFFLINE",
                    changed_at=now,
                    reason="HEARTBEAT_TIMEOUT",
                )
            )
            changed += 1
        db.session.commit()
        return changed
    except SQLAlchemyError:
        db.session.rollback()
        raise


def list_device_statuses():
    return (
        db.session.query(RoomDevice)
        .options(joinedload(RoomDevice.room))
        .order_by(RoomDevice.device_id)
        .all()
    )


def get_device_status(device_id):
    return (
        db.session.query(RoomDevice)
        .options(joinedload(RoomDevice.room))
        .filter_by(device_id=device_id)
        .first()
    )


def list_device_status_history(device_id, *, limit=100):
    return (
        db.session.query(DeviceStatusLog)
        .filter_by(device_id=device_id)
        .order_by(DeviceStatusLog.changed_at.desc(), DeviceStatusLog.device_status_id.desc())
        .limit(limit)
        .all()
    )


def get_device_summary():
    """Summarize registered devices on active rooms for the dashboard."""
    registered = db.session.query(RoomDevice).filter(
        RoomDevice.registration_status == "REGISTERED"
    )
    eligible = (
        registered.join(RoomDevice.room)
        .filter(
            Room.is_active.is_(True),
        )
    )
    counts = {
        status: eligible.filter(RoomDevice.current_status == status).count()
        for status in ("ONLINE", "OFFLINE", "UNKNOWN")
    }
    return {
        "registered_count": registered.count(),
        "active_count": sum(counts.values()),
        "online_count": counts["ONLINE"],
        "offline_count": counts["OFFLINE"],
        "unknown_count": counts["UNKNOWN"],
    }


def serialize_device_status(device):
    return {
        "device_id": device.device_id,
        "device_code": device.device_code,
        "device_name": device.device_name,
        "registration_status": device.registration_status,
        "current_status": device.current_status,
        "last_communication_at": (
            device.last_communication_at.isoformat()
            if device.last_communication_at
            else None
        ),
        "room": (
            {
                "room_id": device.room.room_id,
                "room_number": device.room.room_number,
                "room_name": device.room.room_name,
                "is_active": device.room.is_active,
            }
            if device.room
            else None
        ),
    }


def serialize_status_history(entry):
    return {
        "device_status_id": entry.device_status_id,
        "device_id": entry.device_id,
        "previous_status": entry.previous_status,
        "new_status": entry.new_status,
        "changed_at": entry.changed_at.isoformat() if entry.changed_at else None,
        "reason": entry.reason,
    }
