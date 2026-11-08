from flask import Blueprint, current_app, request
from sqlalchemy.exc import SQLAlchemyError

from api.responses import error_response, service_error_response, success_response
from database.extensions import db, limiter
from services.errors import ServiceError
from services.occupancy.events import create_occupancy_event as record_occupancy_event
from services.security.rate_limits import DEVICE, device_key_func

occupancy_bp = Blueprint("occupancy", __name__, url_prefix="/api/occupancy")


@occupancy_bp.post("/events")
@limiter.limit(DEVICE, key_func=device_key_func)
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
        schema:
          type: object
          required: [room_id, device_id, event_type, occupancy_status]
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
              enum: [AVAILABLE, OCCUPIED]
              example: OCCUPIED
      - in: header
        name: X-Device-Key
        type: string
        required: true
        description: Per-device credential provisioned by an operator
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
                room_id:
                  type: integer
                device_id:
                  type: string
                event_type:
                  type: string
                occupancy_status:
                  type: string
                occurred_at:
                  type: string
                  format: date-time
                  nullable: true
      400:
        description: Invalid request or field values
      404:
        description: Room or room device not found
      500:
        description: Failed to save occupancy event
    """
    if not request.is_json:
        return error_response("Request must use JSON format", 400)

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return error_response("Invalid JSON request body", 400)

    required = ["room_id", "device_id", "event_type", "occupancy_status"]
    missing = [
        field
        for field in required
        if field not in data or data[field] is None or data[field] == ""
    ]
    if missing:
        return error_response("Missing required fields", 400, fields=missing)

    room_id = data["room_id"]
    if isinstance(room_id, bool) or not isinstance(room_id, int):
        return error_response("room_id must be an integer", 400)
    for field in ("device_id", "event_type"):
        if not isinstance(data[field], str) or not data[field].strip():
            return error_response(f"{field} must be a non-empty string", 400)
    if not isinstance(data["occupancy_status"], str):
        return error_response("occupancy_status must be a string", 400)

    status = data["occupancy_status"].strip().upper()
    if status not in {"OCCUPIED", "AVAILABLE"}:
        return error_response(
            "Invalid occupancy_status",
            400,
            allowed_values=["AVAILABLE", "OCCUPIED"],
        )
    data["occupancy_status"] = status

    try:
        event = record_occupancy_event(data, request.headers.get("X-Device-Key"))
    except ServiceError as error:
        return service_error_response(error)
    except SQLAlchemyError as error:
        db.session.rollback()
        current_app.logger.error(
            "Database operation occupancy.create failed (%s)",
            type(error).__name__,
        )
        return error_response("Failed to save occupancy event", 500)

    return success_response(
        {
            "message": "Occupancy event recorded successfully",
            "event": {
                "occupancy_event_id": event.occupancy_event_id,
                "room_id": event.room_id,
                "device_id": event.device_id,
                "event_type": event.event_type,
                "occupancy_status": event.occupancy_status,
                "occurred_at": (
                    event.occurred_at.isoformat() if event.occurred_at else None
                ),
            },
        },
        201,
    )
