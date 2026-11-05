from datetime import datetime

from flask import Blueprint, jsonify, request
from sqlalchemy.exc import SQLAlchemyError

from database.extensions import db
from database.models.occupancy_event import OccupancyEvent
from database.models.room_device import RoomDevice

gateway_bp = Blueprint("gateway", __name__, url_prefix="/api/gateway")


@gateway_bp.post("/messages")
def receive_gateway_message():
    if not request.is_json:
        return jsonify({"error": "Request must use JSON format"}), 400

    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({"error": "Invalid JSON request body"}), 400

    required_fields = [
        "gateway_id",
        "device_id",
        "event_type",
        "occupancy_status",
        "timestamp",
    ]

    missing_fields = [
        field
        for field in required_fields
        if field not in data or data[field] is None or data[field] == ""
    ]

    if missing_fields:
        return jsonify(
            {"error": "Missing required fields", "fields": missing_fields}
        ), 400

    gateway_id = data["gateway_id"]
    device_id = data["device_id"]
    event_type = data["event_type"]
    occupancy_status = data["occupancy_status"]
    timestamp = data["timestamp"]

    if not isinstance(gateway_id, str) or not gateway_id.strip():
        return jsonify({"error": "Invalid gateway_id"}), 400

    if not isinstance(device_id, str) or not device_id.strip():
        return jsonify({"error": "Invalid device_id"}), 400

    if not isinstance(event_type, str) or not event_type.strip():
        return jsonify({"error": "Invalid event_type"}), 400

    if not isinstance(occupancy_status, str):
        return jsonify({"error": "occupancy_status must be a string"}), 400

    occupancy_status = occupancy_status.strip().upper()

    if occupancy_status not in {"AVAILABLE", "OCCUPIED"}:
        return jsonify(
            {
                "error": "Invalid occupancy_status",
                "allowed_values": ["AVAILABLE", "OCCUPIED"],
            }
        ), 400

    if not isinstance(timestamp, str):
        return jsonify({"error": "timestamp must be an ISO 8601 string"}), 400

    try:
        occurred_at = datetime.fromisoformat(timestamp.strip())

        if occurred_at.tzinfo is None:
            raise ValueError("Timezone information is required")

    except ValueError:
        return jsonify(
            {"error": "Invalid timestamp. Use ISO 8601 format with timezone."}
        ), 400

    gateway_id = gateway_id.strip()
    device_id = device_id.strip()

    try:
        device = db.session.get(RoomDevice, device_id)

        if device is None:
            return jsonify(
                {"error": "Room device not found", "device_id": device_id}
            ), 404

        if device.registration_status != "ACTIVE":
            return jsonify(
                {"error": "Room device is not active", "device_id": device_id}
            ), 403

        room = device.room

        if room is None:
            return jsonify({"error": "Registered room not found"}), 404

        event = OccupancyEvent(
            room_id=device.room_id,
            device_id=device.device_id,
            event_type=event_type.strip(),
            occupancy_status=occupancy_status,
            occurred_at=occurred_at,
        )

        room.occupancy_status = occupancy_status
        room.last_occupancy_update = occurred_at

        db.session.add(event)
        db.session.commit()

        return jsonify(
            {
                "message": "Gateway message processed successfully",
                "gateway_id": gateway_id,
                "event": {
                    "occupancy_event_id": event.occupancy_event_id,
                    "room_id": event.room_id,
                    "device_id": event.device_id,
                    "event_type": event.event_type,
                    "occupancy_status": event.occupancy_status,
                    "occurred_at": event.occurred_at.isoformat(),
                },
            }
        ), 201

    except SQLAlchemyError:
        db.session.rollback()

        return jsonify(
            {"error": "Database error while processing gateway message"}
        ), 500
