
from flask import Blueprint, jsonify
from sqlalchemy.exc import SQLAlchemyError

from database.extensions import db
from database.models.room_device import RoomDevice
from database.models.occupancy_event import OccupancyEvent


device_bp = Blueprint(
    "device_management",
    __name__,
    url_prefix="/api/devices"
)


def serialize_device(device):
    room = device.room

    latest_event = (
        db.session.query(OccupancyEvent)
        .filter_by(device_id=device.device_id)
        .order_by(
            OccupancyEvent.occurred_at.desc(),
            OccupancyEvent.occupancy_event_id.desc()
        )
        .first()
    )

    return {
        "device_id": device.device_id,
        "device_code": device.device_code,
        "device_name": device.device_name,
        "registration_status": device.registration_status,
        "registered_at": (
            device.registered_at.isoformat()
            if device.registered_at else None
        ),
        "room": {
            "room_id": room.room_id,
            "room_number": room.room_number,
            "room_name": room.room_name,
            "occupancy_status": room.occupancy_status,
            "is_active": room.is_active
        } if room else None,
        "latest_occupancy_event": {
            "occupancy_event_id": latest_event.occupancy_event_id,
            "event_type": latest_event.event_type,
            "occupancy_status": latest_event.occupancy_status,
            "occurred_at": (
                latest_event.occurred_at.isoformat()
                if latest_event.occurred_at else None
            )
        } if latest_event else None
    }


# GET ALL ROOM DEVICES
@device_bp.get("/")
def get_all_devices():
    try:
        devices = (
            db.session.query(RoomDevice)
            .order_by(RoomDevice.device_id.asc())
            .all()
        )

        return jsonify({
            "message": "Room devices retrieved successfully",
            "count": len(devices),
            "devices": [
                serialize_device(device)
                for device in devices
            ]
        }), 200

    except SQLAlchemyError:
        db.session.rollback()
        return jsonify({
            "error": "Database error while retrieving room devices"
        }), 500


# GET ROOM DEVICE BY ID
@device_bp.get("/<string:device_id>")
def get_device_by_id(device_id):
    try:
        device = db.session.get(RoomDevice, device_id)

        if device is None:
            return jsonify({
                "error": "Room device not found",
                "device_id": device_id
            }), 404

        return jsonify({
            "message": "Room device retrieved successfully",
            "device": serialize_device(device)
        }), 200

    except SQLAlchemyError:
        db.session.rollback()
        return jsonify({
            "error": "Database error while retrieving room device"
        }), 500
