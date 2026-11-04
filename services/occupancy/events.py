import hashlib
import hmac

from sqlalchemy.exc import SQLAlchemyError

from database.extensions import db
from database.models.occupancy_event import OccupancyEvent
from database.models.room import Room
from database.models.room_device import RoomDevice
from services.errors import (
    AssociationError,
    InactiveDeviceError,
    InvalidDeviceCredentialsError,
    NotFoundError,
)


def authenticate_device(device_id, credential):
    try:
        device = db.session.get(RoomDevice, device_id)
        if device is None or not device.credential_hash or not credential:
            raise InvalidDeviceCredentialsError("Invalid device credentials")
        if not isinstance(credential, str):
            raise InvalidDeviceCredentialsError("Invalid device credentials")
        credential_hash = hashlib.sha256(credential.encode("utf-8")).hexdigest()
        if not hmac.compare_digest(device.credential_hash, credential_hash):
            raise InvalidDeviceCredentialsError("Invalid device credentials")
        if (device.registration_status or "").upper() != "REGISTERED":
            raise InactiveDeviceError("Device is not registered")
        return device
    except SQLAlchemyError:
        db.session.rollback()
        raise


def create_occupancy_event(data, credential):
    try:
        device_id = data["device_id"].strip()
        device = authenticate_device(device_id, credential)
        room = db.session.get(Room, data["room_id"])
        if room is None:
            raise NotFoundError("Room not found", details={"room_id": data["room_id"]})
        if device.room_id != room.room_id:
            raise AssociationError("The device is not registered to this room")

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
