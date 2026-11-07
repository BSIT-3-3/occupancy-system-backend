import hashlib
import hmac

from sqlalchemy.exc import SQLAlchemyError

from database.extensions import db
from database.models.room_device import RoomDevice
from services.errors import InactiveDeviceError, InvalidDeviceCredentialsError


def authenticate_device(device_id, credential, *, lock=False):
    """Validate a device key and registration state before accepting messages."""
    try:
        query = db.session.query(RoomDevice).filter_by(device_id=device_id)
        if lock:
            query = query.with_for_update()
        device = query.first()

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
