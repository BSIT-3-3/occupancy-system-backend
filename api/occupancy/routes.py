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


@occupancy_bp.post("/events")
def create_occupancy_event():
    """
    Record an occupancy event.
    ---
    tags:
      - Occupancy
    consumes:
      - application/json
    produces:
      - application/json
    parameters:
      - in: body
        name: body
        required: true
        description: Occupancy event details sent by a room device
        schema:
          type: object
          required:
            - room_id
            - device_id
            - event_type
            - occupancy_status
          properties:
            room_id:
              type: integer
              example: 1
            device_id:
              type: string
              example: ROOM-001-DEVICE
            event_type:
              type: string
              example: MOTION_DETECTED
            occupancy_status:
              type: string
              enum:
                - AVAILABLE
                - OCCUPIED
              example: OCCUPIED
    responses:
      201:
        description: Occupancy event recorded successfully
        schema:
          type: object
          properties:
            message:
              type: string
              example: Occupancy event recorded successfully
            event:
              type: object
              properties:
                occupancy_event_id:
                  type: integer
                  example: 1
                room_id:
                  type: integer
                  example: 1
                device_id:
                  type: string
                  example: ROOM-001-DEVICE
                event_type:
                  type: string
                  example: MOTION_DETECTED
                occupancy_status:
                  type: string
                  example: OCCUPIED
                occurred_at:
                  type: string
                  format: date-time
                  nullable: true
      400:
        description: Invalid JSON, missing fields, or invalid field values
      404:
        description: Room or room device not found
      500:
        description: Failed to save occupancy event
    """
    if not request.is_json:
        return jsonify({"error": "Request must use JSON format"}), 400

    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({"error": "Invalid JSON request body"}), 400

    required_fields = [
        "room_id",
        "device_id",
        "event_type",
        "occupancy_status"
    ]

    missing_fields = [
        field for field in required_fields
        if field not in data or data[field] is None or data[field] == ""
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
        return jsonify({"error": "room_id must be an integer"}), 400

    if not isinstance(device_id, str) or not device_id.strip():
        return jsonify({"error": "device_id must be a non-empty string"}), 400

    if not isinstance(event_type, str) or not event_type.strip():
        return jsonify({"error": "event_type must be a non-empty string"}), 400

    if not isinstance(occupancy_status, str):
        return jsonify({"error": "occupancy_status must be a string"}), 400

    occupancy_status = occupancy_status.strip().upper()

    if occupancy_status not in {"OCCUPIED", "AVAILABLE"}:
        return jsonify({
            "error": "Invalid occupancy_status",
            "allowed_values": ["AVAILABLE", "OCCUPIED"]
        }), 400

    room = db.session.get(Room, room_id)

    if room is None:
        return jsonify({"error": "Room not found", "room_id": room_id}), 404

    device_id = device_id.strip()
    device = db.session.get(RoomDevice, device_id)

    if device is None:
        return jsonify({"error": "Room device not found", "device_id": device_id}), 404

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
        return jsonify({"error": "Failed to save occupancy event"}), 500

    return jsonify({
        "message": "Occupancy event recorded successfully",
        "event": {
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
    }), 201