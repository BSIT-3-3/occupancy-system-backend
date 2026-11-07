from datetime import UTC, datetime

from sqlalchemy.exc import SQLAlchemyError

from database.extensions import db
from database.models.occupancy_event import OccupancyEvent
from database.models.room import Room
from services.errors import (
    AssociationError,
    InactiveRoomError,
    NotFoundError,
)
from services.security.device_auth import authenticate_device


def create_occupancy_event(data, credential):
    try:
        device_id = data["device_id"].strip()
        device = authenticate_device(device_id, credential)
        room = db.session.get(Room, data["room_id"])
        if room is None:
            raise NotFoundError("Room not found", details={"room_id": data["room_id"]})
        if device.room_id != room.room_id:
            raise AssociationError("The device is not registered to this room")
        if not room.is_active:
            raise InactiveRoomError("Room is inactive")

        now = datetime.now(UTC)
        room.occupancy_status = data["occupancy_status"]
        room.last_occupancy_update = now
        event = OccupancyEvent(
            room_id=device.room_id,
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
