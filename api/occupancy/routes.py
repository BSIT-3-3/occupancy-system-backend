
from flask import Blueprint, jsonify, request

from database.extensions import db
from database.models.room import Room
from database.models.room_device import RoomDevice
from database.models.occupancy_event import OccupancyEvent


occupancy_bp = Blueprint(
    "occupancy",
    __name__,
    url_prefix="/api/occupancy"
)


def serialize_event(event):
    return {
        "occupancy_event_id": event.occupancy_event_id,
        "room_id": event.room_id,
        "device_id": event.device_id,
        "event_type": event.event_type,
        "occupancy_status": event.occupancy_status,
        "occurred_at": (
            event.occurred_at.isoformat()
            if event.occurred_at else None
        )
    }


# POST: CREATE A NEW OCCUPANCY EVENT
@occupancy_bp.post("/events")
def create_occupancy_event():
    if not request.is_json:
        return jsonify({
            "error": "Request must use JSON format"
        }), 400

    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({
            "error": "Invalid JSON request body"
        }), 400

    required_fields = [
        "room_id",
        "device_id",
        "event_type",
        "occupancy_status"
    ]

    missing_fields = [
        field for field in required_fields
        if field not in data
        or data[field] is None
        or data[field] == ""
    ]

    if missing_fields:
        return jsonify({
            "error": "Missing required fields",
            "fields": missing_fields
        }), 400

    room_id = data["room_id"]
    device_id = data["device_id"]
    event_type = data["event_type"]
    occupancy_status = data["occupancy_status"]

    if isinstance(room_id, bool) or not isinstance(room_id, int):
        return jsonify({
            "error": "room_id must be an integer"
        }), 400

    if not isinstance(device_id, str) or not device_id.strip():
        return jsonify({
            "error": "device_id must be a non-empty string"
        }), 400

    if not isinstance(event_type, str) or not event_type.strip():
        return jsonify({
            "error": "event_type must be a non-empty string"
        }), 400

    if not isinstance(occupancy_status, str):
        return jsonify({
            "error": "occupancy_status must be a string"
        }), 400

    occupancy_status = occupancy_status.strip().upper()

    if occupancy_status not in {"OCCUPIED", "AVAILABLE"}:
        return jsonify({
            "error": "Invalid occupancy_status",
            "allowed_values": ["AVAILABLE", "OCCUPIED"]
        }), 400

    room = db.session.get(Room, room_id)

    if room is None:
        return jsonify({
            "error": "Room not found",
            "room_id": room_id
        }), 404

    device_id = device_id.strip()
    device = db.session.get(RoomDevice, device_id)

    if device is None:
        return jsonify({
            "error": "Room device not found",
            "device_id": device_id
        }), 404

    if device.room_id != room.room_id:
        return jsonify({
            "error": "The device is not registered to this room"
        }), 400

    event = OccupancyEvent(
        room_id=room.room_id,
        device_id=device.device_id,
        event_type=event_type.strip(),
        occupancy_status=occupancy_status
    )

    try:
        db.session.add(event)
        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify({
            "error": "Failed to save occupancy event"
        }), 500

    return jsonify({
        "message": "Occupancy event recorded successfully",
        "event": serialize_event(event)
    }), 201


# GET: RETRIEVE ALL OCCUPANCY EVENTS
@occupancy_bp.get("/events")
def get_occupancy_events():
    events = OccupancyEvent.query.order_by(
        OccupancyEvent.occupancy_event_id.desc()
    ).all()

    return jsonify({
        "count": len(events),
        "events": [serialize_event(event) for event in events]
    }), 200


# GET BY ID: RETRIEVE ONE OCCUPANCY EVENT
@occupancy_bp.get("/events/<int:event_id>")
def get_occupancy_event(event_id):
    event = db.session.get(OccupancyEvent, event_id)

    if event is None:
        return jsonify({
            "error": "Occupancy event not found",
            "occupancy_event_id": event_id
        }), 404

    return jsonify({
        "event": serialize_event(event)
    }), 200


# PUT BY ID: UPDATE AN OCCUPANCY EVENT
@occupancy_bp.put("/events/<int:event_id>")
def update_occupancy_event(event_id):
    event = db.session.get(OccupancyEvent, event_id)

    if event is None:
        return jsonify({
            "error": "Occupancy event not found",
            "occupancy_event_id": event_id
        }), 404

    if not request.is_json:
        return jsonify({
            "error": "Request must use JSON format"
        }), 400

    data = request.get_json(silent=True)

    if not isinstance(data, dict) or not data:
        return jsonify({
            "error": "A non-empty JSON object is required"
        }), 400

    allowed_fields = {
        "room_id",
        "device_id",
        "event_type",
        "occupancy_status"
    }

    invalid_fields = set(data.keys()) - allowed_fields

    if invalid_fields:
        return jsonify({
            "error": "Invalid update fields",
            "fields": sorted(invalid_fields)
        }), 400

    new_room_id = event.room_id
    new_device_id = event.device_id

    if "room_id" in data:
        room_id = data["room_id"]

        if isinstance(room_id, bool) or not isinstance(room_id, int):
            return jsonify({
                "error": "room_id must be an integer"
            }), 400

        room = db.session.get(Room, room_id)

        if room is None:
            return jsonify({
                "error": "Room not found",
                "room_id": room_id
            }), 404

        new_room_id = room.room_id

    if "device_id" in data:
        device_id = data["device_id"]

        if not isinstance(device_id, str) or not device_id.strip():
            return jsonify({
                "error": "device_id must be a non-empty string"
            }), 400

        new_device_id = device_id.strip()

    device = db.session.get(RoomDevice, new_device_id)

    if device is None:
        return jsonify({
            "error": "Room device not found",
            "device_id": new_device_id
        }), 404

    if device.room_id != new_room_id:
        return jsonify({
            "error": "The device is not registered to this room"
        }), 400

    if "event_type" in data:
        event_type = data["event_type"]

        if not isinstance(event_type, str) or not event_type.strip():
            return jsonify({
                "error": "event_type must be a non-empty string"
            }), 400

        event.event_type = event_type.strip()

    if "occupancy_status" in data:
        status = data["occupancy_status"]

        if not isinstance(status, str):
            return jsonify({
                "error": "occupancy_status must be a string"
            }), 400

        status = status.strip().upper()

        if status not in {"OCCUPIED", "AVAILABLE"}:
            return jsonify({
                "error": "Invalid occupancy_status",
                "allowed_values": ["AVAILABLE", "OCCUPIED"]
            }), 400

        event.occupancy_status = status

    event.room_id = new_room_id
    event.device_id = new_device_id

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify({
            "error": "Failed to update occupancy event"
        }), 500

    return jsonify({
        "message": "Occupancy event updated successfully",
        "event": serialize_event(event)
    }), 200


# DELETE BY ID: DELETE AN OCCUPANCY EVENT
@occupancy_bp.delete("/events/<int:event_id>")
def delete_occupancy_event(event_id):
    event = db.session.get(OccupancyEvent, event_id)

    if event is None:
        return jsonify({
            "error": "Occupancy event not found",
            "occupancy_event_id": event_id
        }), 404

    try:
        db.session.delete(event)
        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify({
            "error": "Failed to delete occupancy event"
        }), 500

    return jsonify({
        "message": "Occupancy event deleted successfully",
        "occupancy_event_id": event_id
    }), 200
