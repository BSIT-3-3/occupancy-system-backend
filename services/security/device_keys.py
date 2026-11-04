import hashlib
import secrets

from sqlalchemy.exc import SQLAlchemyError

from database.extensions import db
from database.models.room_device import RoomDevice
from services.errors import InactiveDeviceError, NotFoundError


def provision_device_key(device_id, *, activate=False):
    try:
        device = db.session.get(RoomDevice, device_id)
        if device is None:
            raise NotFoundError("Room device not found")
        if (device.registration_status or "").upper() != "REGISTERED":
            if not activate:
                raise InactiveDeviceError(
                    "Device must be activated before a key can be provisioned"
                )
            device.registration_status = "REGISTERED"

        credential = secrets.token_urlsafe(32)
        device.credential_hash = hashlib.sha256(
            credential.encode("utf-8")
        ).hexdigest()
        db.session.commit()
        return credential
    except SQLAlchemyError:
        db.session.rollback()
        raise
