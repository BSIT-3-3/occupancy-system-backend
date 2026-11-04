from sqlalchemy.exc import SQLAlchemyError

from database.extensions import db
from database.models.occupancy_event import OccupancyEvent
from database.models.room import Room
from database.models.room_device import RoomDevice
from services.errors import AssociationError, NotFoundError


def create_occupancy_event(data):
    try:
        room = db.session.get(Room, data["room_id"])
        if room is None:
            raise NotFoundError("Room not found", details={"room_id": data["room_id"]})

        device_id = data["device_id"].strip()
        device = db.session.get(RoomDevice, device_id)
        if device is None:
            raise NotFoundError("Room device not found", details={"device_id": device_id})
        if device.room_id != room.room_id:
            raise AssociationError("The device is not registered to this room")

        event = OccupancyEvent(
            room_id=room.room_id,
            device_id=device.device_id,
            event_type=data["event_type"].strip(),
            occupancy_status=data["occupancy_status"],
        )
        db.session.add(event)
        db.session.commit()
        return event
    except SQLAlchemyError:
        db.session.rollback()
        raise
