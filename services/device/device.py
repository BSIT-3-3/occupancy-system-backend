from sqlalchemy.exc import SQLAlchemyError

from database.extensions import db
from database.models.room import Room
from database.models.room_device import RoomDevice
from services.errors import ConflictError, NotFoundError


def list_devices():
    return db.session.query(RoomDevice).order_by(RoomDevice.device_id).all()


def get_device(device_id):
    return db.session.get(RoomDevice, device_id)


def list_available_rooms():
    """Active rooms that do not yet have a device assigned.

    The schema enforces one device per room, so only rooms without any device
    record are eligible for a new assignment.
    """
    assigned_room_ids = db.session.query(RoomDevice.room_id).scalar_subquery()
    return (
        db.session.query(Room)
        .filter(Room.is_active.is_(True))
        .filter(~Room.room_id.in_(assigned_room_ids))
        .order_by(Room.room_number, Room.room_id)
        .all()
    )


def create_device(data):
    try:
        if (
            db.session.query(RoomDevice.device_id)
            .filter_by(device_id=data["device_id"])
            .first()
            is not None
        ):
            raise ConflictError("Device ID already exists")

        if (
            db.session.query(RoomDevice.device_id)
            .filter_by(device_code=data["device_code"])
            .first()
            is not None
        ):
            raise ConflictError("Device code already exists")

        room = _resolve_room(data["room_id"])

        device = RoomDevice(
            device_id=data["device_id"],
            room_id=room.room_id,
            device_code=data["device_code"],
            device_name=data.get("device_name"),
            registration_status="PENDING",
        )
        db.session.add(device)
        db.session.commit()
        return device
    except SQLAlchemyError:
        db.session.rollback()
        raise


def update_device(device, data):
    try:
        if "device_code" in data:
            duplicate = (
                db.session.query(RoomDevice.device_id)
                .filter(
                    RoomDevice.device_code == data["device_code"],
                    RoomDevice.device_id != device.device_id,
                )
                .first()
            )
            if duplicate is not None:
                raise ConflictError("Device code already exists")
            device.device_code = data["device_code"]

        if "device_name" in data:
            device.device_name = data["device_name"]

        if "room_id" in data:
            room = _resolve_room(data["room_id"], exclude_device_id=device.device_id)
            device.room_id = room.room_id

        if "registration_status" in data:
            device.registration_status = data["registration_status"]

        db.session.commit()
        return device
    except SQLAlchemyError:
        db.session.rollback()
        raise


def deactivate_device(device):
    try:
        device.registration_status = "DEACTIVATED"
        db.session.commit()
        return device
    except SQLAlchemyError:
        db.session.rollback()
        raise


def _resolve_room(room_id, *, exclude_device_id=None):
    """Validate a room for device assignment.

    The room must exist, be active, and not already have another device
    assigned to it. ``exclude_device_id`` lets a device keep its own room
    during updates.
    """
    room = db.session.get(Room, room_id)
    if room is None:
        raise NotFoundError("Room not found", details={"room_id": room_id})
    if not room.is_active:
        raise ConflictError("Room is inactive")

    existing = (
        db.session.query(RoomDevice.device_id)
        .filter(
            RoomDevice.room_id == room_id,
            RoomDevice.device_id != exclude_device_id,
        )
        .first()
    )
    if existing is not None:
        raise ConflictError("Room already has a device assigned")

    return room
