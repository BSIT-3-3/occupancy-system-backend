from flask import Blueprint
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from api.authentication.validation import (
    validate_json_request,
    validate_string_field,
)
from api.responses import (
    database_error_response,
    error_response,
    service_error_response,
    success_response,
)
from api.security import admin_required
from database.extensions import limiter
from services.errors import ServiceError
from services.room import room as room_service
from services.security.rate_limits import READ, WRITE

room_management_bp = Blueprint("room_management", __name__)

_ROOM_FIELDS = {"room_number", "room_name", "is_active"}


def _validate_room_payload(*, required_fields=()):
    data, error = validate_json_request(required_fields)
    if error:
        return None, error

    unsupported = set(data) - _ROOM_FIELDS
    if unsupported:
        return None, error_response(
            "Unsupported fields", 400, fields=sorted(unsupported)
        )
    if not data:
        return None, error_response("At least one field is required", 400)

    for field in ("room_number", "room_name"):
        if field not in data:
            continue
        data[field], error = validate_string_field(data, field)
        if error:
            return None, error
        if len(data[field]) > 50:
            return None, error_response(
                f"{field} must not exceed 50 characters", 400
            )

    if "is_active" in data and not isinstance(data["is_active"], bool):
        return None, error_response("is_active must be a boolean", 400)

    return data, None


@room_management_bp.get("/rooms")
@limiter.limit(READ)
@admin_required
def get_rooms():
    """List all rooms, including inactive rooms.
    ---
    tags:
      - Room Management
    security:
      - Bearer: []
    responses:
      200:
        description: Rooms ordered by room number
        schema:
          type: array
          items:
            type: object
            properties:
              room_id:
                type: integer
              room_number:
                type: string
              room_name:
                type: string
              occupancy_status:
                type: string
                enum: [AVAILABLE, OCCUPIED]
              last_occupancy_update:
                type: string
                format: date-time
                x-nullable: true
              is_active:
                type: boolean
      401:
        description: Authentication required
      403:
        description: Administrator access required
      500:
        description: Failed to load rooms
    """
    try:
        rooms = room_service.list_rooms()
        return success_response([room.to_dict() for room in rooms])
    except SQLAlchemyError as error:
        return database_error_response("room.list", error)


@room_management_bp.get("/rooms/<int:room_id>")
@limiter.limit(READ)
@admin_required
def get_room(room_id):
    """Get one room by its ID.
    ---
    tags:
      - Room Management
    security:
      - Bearer: []
    parameters:
      - in: path
        name: room_id
        type: integer
        required: true
    responses:
      200:
        description: Room details
      401:
        description: Authentication required
      403:
        description: Administrator access required
      404:
        description: Room not found
    """
    try:
        room = room_service.get_room(room_id)
        if room is None:
            return error_response("Room not found", 404)
        return success_response(room.to_dict())
    except SQLAlchemyError as error:
        return database_error_response("room.get", error)


@room_management_bp.post("/rooms")
@limiter.limit(WRITE)
@admin_required
def create_room():
    """Create a room. New rooms begin as AVAILABLE.
    ---
    tags:
      - Room Management
    security:
      - Bearer: []
    consumes:
      - application/json
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required: [room_number, room_name]
          properties:
            room_number:
              type: string
              maxLength: 50
              example: "101"
            room_name:
              type: string
              maxLength: 50
              example: Computer Laboratory
            is_active:
              type: boolean
              default: true
    responses:
      201:
        description: Room created
      400:
        description: Invalid input
      401:
        description: Authentication required
      403:
        description: Administrator access required
      409:
        description: Room number already exists
    """
    data, error = _validate_room_payload(
        required_fields=("room_number", "room_name")
    )
    if error:
        return error

    try:
        room = room_service.create_room(data)
    except ServiceError as error:
        return service_error_response(error)
    except IntegrityError as error:
        return database_error_response(
            "room.create", error, conflict_message="Room number already exists"
        )
    except SQLAlchemyError as error:
        return database_error_response("room.create", error)

    return success_response(room.to_dict(), 201)


def _update_room(room_id, *, partial):
    try:
        room = room_service.get_room(room_id)
    except SQLAlchemyError as error:
        return database_error_response("room.get", error)
    if room is None:
        return error_response("Room not found", 404)

    required = () if partial else ("room_number", "room_name")
    data, error = _validate_room_payload(required_fields=required)
    if error:
        return error

    try:
        room = room_service.update_room(room, data)
    except ServiceError as error:
        return service_error_response(error)
    except IntegrityError as error:
        return database_error_response(
            "room.update", error, conflict_message="Room number already exists"
        )
    except SQLAlchemyError as error:
        return database_error_response("room.update", error)

    return success_response(room.to_dict())


@room_management_bp.put("/rooms/<int:room_id>")
@limiter.limit(WRITE)
@admin_required
def replace_room(room_id):
    """Replace the editable room fields.
    ---
    tags:
      - Room Management
    security:
      - Bearer: []
    consumes:
      - application/json
    parameters:
      - in: path
        name: room_id
        type: integer
        required: true
      - in: body
        name: body
        required: true
        schema:
          type: object
          required: [room_number, room_name]
          properties:
            room_number:
              type: string
              maxLength: 50
            room_name:
              type: string
              maxLength: 50
            is_active:
              type: boolean
    responses:
      200:
        description: Room updated
      400:
        description: Invalid input
      404:
        description: Room not found
      409:
        description: Room number already exists
    """
    return _update_room(room_id, partial=False)


@room_management_bp.patch("/rooms/<int:room_id>")
@limiter.limit(WRITE)
@admin_required
def patch_room(room_id):
    """Update selected editable room fields.
    ---
    tags:
      - Room Management
    security:
      - Bearer: []
    consumes:
      - application/json
    parameters:
      - in: path
        name: room_id
        type: integer
        required: true
      - in: body
        name: body
        required: true
        schema:
          type: object
          properties:
            room_number:
              type: string
              maxLength: 50
            room_name:
              type: string
              maxLength: 50
            is_active:
              type: boolean
    responses:
      200:
        description: Room updated
      400:
        description: Invalid input
      404:
        description: Room not found
      409:
        description: Room number already exists
    """
    return _update_room(room_id, partial=True)


@room_management_bp.delete("/rooms/<int:room_id>")
@limiter.limit(WRITE)
@admin_required
def delete_room(room_id):
    """Deactivate a room while preserving sensor and occupancy history.
    ---
    tags:
      - Room Management
    security:
      - Bearer: []
    responses:
      200:
        description: Room deactivated; its history is preserved
      401:
        description: Authentication required
      403:
        description: Administrator access required
      404:
        description: Room not found
    """
    try:
        room = room_service.get_room(room_id)
        if room is None:
            return error_response("Room not found", 404)
        room_service.deactivate_room(room)
        return success_response({"message": "Room deactivated", "room_id": room_id})
    except SQLAlchemyError as error:
        return database_error_response("room.deactivate", error)
