from flask import Blueprint, current_app, request
from sqlalchemy.exc import SQLAlchemyError


from api.responses import error_response, service_error_response, success_response
from database.extensions import db, limiter
from services.errors import ServiceError
from services.occupancy.events import create_occupancy_event as record_occupancy_event
from services.security.rate_limits import DEVICE, device_key_func
from api.responses import error_response, success_response
from api.security import admin_required
from database.extensions import db
from database.models.occupancy_event import OccupancyEvent
from database.models.room import Room
from database.models.room_device import RoomDevice
from services.errors import (
    AssociationError,
    InactiveDeviceError,
    InvalidDeviceCredentialsError,
    NotFoundError,
    ServiceError,
)
from services.occupancy.events import (
    create_occupancy_event as record_occupancy_event,
)

occupancy_bp = Blueprint("occupancy", __name__, url_prefix="/api/occupancy")


def serialize_event(event):
    return {
        "occupancy_event_id": event.occupancy_event_id,
        "room_id": event.room_id,
        "device_id": event.device_id,
        "event_type": event.event_type,
        "occupancy_status": event.occupancy_status,
        "occurred_at": (event.occurred_at.isoformat() if event.occurred_at else None),
    }


def handle_service_error(error):
    if isinstance(error, NotFoundError):
        return error_response(str(error), 404, **error.details)

    if isinstance(error, InvalidDeviceCredentialsError):
        return error_response(str(error), 401, **error.details)

    if isinstance(error, InactiveDeviceError):
        return error_response(str(error), 403, **error.details)

    if isinstance(error, AssociationError):
        return error_response(str(error), 400, **error.details)

    return error_response(str(error), 400, **error.details)


# POST: CREATE A NEW OCCUPANCY EVENT
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
      400:
        description: Invalid request or field values
      401:
        description: Invalid device credentials
      403:
        description: Inactive device
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

    if isinstance(data["room_id"], bool) or not isinstance(data["room_id"], int):
        return error_response("room_id must be an integer", 400)

    for field in ("device_id", "event_type"):
        if not isinstance(data[field], str) or not data[field].strip():
            return error_response(f"{field} must be a non-empty string", 400)

    if not isinstance(data["occupancy_status"], str):
        return error_response("occupancy_status must be a string", 400)

    status = data["occupancy_status"].strip().upper()

    if status not in {"AVAILABLE", "OCCUPIED"}:
        return error_response(
            "Invalid occupancy_status",
            400,
            allowed_values=["AVAILABLE", "OCCUPIED"],
        )

    data["device_id"] = data["device_id"].strip()
    data["event_type"] = data["event_type"].strip()
    data["occupancy_status"] = status

    try:
        event = record_occupancy_event(
            data,
            request.headers.get("X-Device-Key"),
        )

        return success_response(
            {
                "message": "Occupancy event recorded successfully",
                "event": serialize_event(event),
            },
            201,
        )

    except ServiceError as error:
        return handle_service_error(error)

    except SQLAlchemyError as error:
        db.session.rollback()
        current_app.logger.error(
            "Database operation occupancy.create failed (%s)",
            type(error).__name__,
        )
        return error_response("Failed to save occupancy event", 500)


# GET: RETRIEVE OCCUPANCY EVENT HISTORY
@occupancy_bp.get("/events")
@admin_required
def get_occupancy_events():
    limit_value = request.args.get("limit", "50")

    try:
        limit = int(limit_value)
    except (TypeError, ValueError):
        return error_response("limit must be an integer", 400)

    if not 1 <= limit <= 100:
        return error_response("limit must be between 1 and 100", 400)

    events = (
        OccupancyEvent.query.order_by(
            OccupancyEvent.occurred_at.desc(),
            OccupancyEvent.occupancy_event_id.desc(),
        )
        .limit(limit)
        .all()
    )

    return success_response(
        {
            "count": len(events),
            "events": [serialize_event(event) for event in events],
        },
        200,
    )


# GET BY ID: RETRIEVE ONE OCCUPANCY EVENT
@occupancy_bp.get("/events/<int:event_id>")
def get_occupancy_event(event_id):
    event = db.session.get(OccupancyEvent, event_id)

    if event is None:
        return error_response(
            "Occupancy event not found",
            404,
            occupancy_event_id=event_id,
        )

    return success_response({"event": serialize_event(event)}, 200)


# PUT BY ID: UPDATE AN OCCUPANCY EVENT
@occupancy_bp.put("/events/<int:event_id>")
def update_occupancy_event(event_id):
    event = db.session.get(OccupancyEvent, event_id)

    if event is None:
        return error_response(
            "Occupancy event not found",
            404,
            occupancy_event_id=event_id,
        )

    if not request.is_json:
        return error_response("Request must use JSON format", 400)

    data = request.get_json(silent=True)

    if not isinstance(data, dict) or not data:
        return error_response("A non-empty JSON object is required", 400)

    allowed_fields = {
        "room_id",
        "device_id",
        "event_type",
        "occupancy_status",
    }

    invalid_fields = set(data.keys()) - allowed_fields

    if invalid_fields:
        return error_response(
            "Invalid update fields",
            400,
            fields=sorted(invalid_fields),
        )

    new_room_id = event.room_id
    new_device_id = event.device_id

    if "room_id" in data:
        room_id = data["room_id"]

        if isinstance(room_id, bool) or not isinstance(room_id, int):
            return error_response("room_id must be an integer", 400)

        room = db.session.get(Room, room_id)

        if room is None:
            return error_response("Room not found", 404, room_id=room_id)

        new_room_id = room.room_id

    if "device_id" in data:
        device_id = data["device_id"]

        if not isinstance(device_id, str) or not device_id.strip():
            return error_response("device_id must be a non-empty string", 400)

        new_device_id = device_id.strip()

    device = db.session.get(RoomDevice, new_device_id)

    if device is None:
        return error_response(
            "Room device not found",
            404,
            device_id=new_device_id,
        )

    if device.room_id != new_room_id:
        return error_response(
            "The device is not registered to this room",
            400,
        )

    if "event_type" in data:
        event_type = data["event_type"]

        if not isinstance(event_type, str) or not event_type.strip():
            return error_response("event_type must be a non-empty string", 400)

        event.event_type = event_type.strip()

    if "occupancy_status" in data:
        status = data["occupancy_status"]

        if not isinstance(status, str):
            return error_response("occupancy_status must be a string", 400)

        status = status.strip().upper()

        if status not in {"OCCUPIED", "AVAILABLE"}:
            return error_response(
                "Invalid occupancy_status",
                400,
                allowed_values=["AVAILABLE", "OCCUPIED"],
            )

        event.occupancy_status = status

    event.room_id = new_room_id
    event.device_id = new_device_id

    try:
        db.session.commit()

    except SQLAlchemyError as error:
        db.session.rollback()
        current_app.logger.error(
            "Database operation occupancy.update failed (%s)",
            type(error).__name__,
        )
        return error_response("Failed to update occupancy event", 500)

    return success_response(
        {
            "message": "Occupancy event updated successfully",
            "event": serialize_event(event),
        },
        200,
    )


# DELETE BY ID: DELETE AN OCCUPANCY EVENT
@occupancy_bp.delete("/events/<int:event_id>")
def delete_occupancy_event(event_id):
    event = db.session.get(OccupancyEvent, event_id)

    if event is None:
        return error_response(
            "Occupancy event not found",
            404,
            occupancy_event_id=event_id,
        )

    try:
        db.session.delete(event)
        db.session.commit()

    except SQLAlchemyError as error:
        db.session.rollback()
        current_app.logger.error(
            "Database operation occupancy.delete failed (%s)",
            type(error).__name__,
        )
        return error_response("Failed to delete occupancy event", 500)

    return success_response(
        {
            "message": "Occupancy event deleted successfully",
            "occupancy_event_id": event_id,
        },
        200,
    )
