from sqlalchemy.exc import SQLAlchemyError

from database.extensions import db
from database.models.room import Room
from database.models.room_device import RoomDevice
from services.errors import ConflictError


def list_rooms():
    return db.session.query(Room).order_by(Room.room_number, Room.room_id).all()


def get_room(room_id):
    return db.session.get(Room, room_id)


def create_room(data):
    try:
        if db.session.query(Room).filter_by(room_number=data["room_number"]).first():
            raise ConflictError("Room number already exists")

        room = Room(
            room_number=data["room_number"],
            room_name=data["room_name"],
            is_active=data.get("is_active", True),
        )
        db.session.add(room)
        db.session.commit()
        return room
    except SQLAlchemyError:
        db.session.rollback()
        raise


def update_room(room, data):
    try:
        if "room_number" in data:
            duplicate = (
                db.session.query(Room.room_id)
                .filter(
                    Room.room_number == data["room_number"],
                    Room.room_id != room.room_id,
                )
                .first()
            )
            if duplicate:
                raise ConflictError("Room number already exists")
            room.room_number = data["room_number"]

        if "room_name" in data:
            room.room_name = data["room_name"]
        if "is_active" in data:
            room.is_active = data["is_active"]
            if data["is_active"] is False:
                _deactivate_assigned_device(room)

        db.session.commit()
        return room
    except SQLAlchemyError:
        db.session.rollback()
        raise


def deactivate_room(room):
    try:
        room.is_active = False
        _deactivate_assigned_device(room)
        db.session.commit()
        return room
    except SQLAlchemyError:
        db.session.rollback()
        raise


def _deactivate_assigned_device(room):
    """Deactivate the device assigned to a room when the room becomes inactive.

    The device record and its room link are preserved (the room_id stays set);
    only its lifecycle status changes so a device never remains actively
    assigned to an inactive room. Reactivating the room does not automatically
    reactivate the device.

    The device is looked up directly by room_id rather than via the Room.device
    backref, which keeps the lookup explicit and independent of relationship
    loading state.
    """
    device = (
        db.session.query(RoomDevice)
        .filter(RoomDevice.room_id == room.room_id)
        .first()
    )
    if device is not None:
        device.registration_status = "DEACTIVATED"
