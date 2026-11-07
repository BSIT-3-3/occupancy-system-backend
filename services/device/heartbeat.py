from datetime import UTC, datetime

from sqlalchemy.exc import SQLAlchemyError

from database.extensions import db
from database.models.device_status_log import DeviceStatusLog
from services.errors import InactiveDeviceError
from services.security.device_auth import authenticate_device


def record_heartbeat(device_id, credential):
    """Record a valid heartbeat and log only an actual transition to ONLINE."""
    try:
        device = authenticate_device(device_id, credential, lock=True)
        if device.room is None or not device.room.is_active:
            raise InactiveDeviceError("Device is not registered to an active room")

        now = datetime.now(UTC)
        previous_status = device.current_status
        device.last_communication_at = now

        if previous_status != "ONLINE":
            device.current_status = "ONLINE"
            db.session.add(
                DeviceStatusLog(
                    device_id=device.device_id,
                    previous_status=previous_status,
                    new_status="ONLINE",
                    changed_at=now,
                    reason="HEARTBEAT",
                )
            )

        db.session.commit()
        return device
    except SQLAlchemyError:
        db.session.rollback()
        raise
