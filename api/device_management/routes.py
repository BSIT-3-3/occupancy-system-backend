from flask import Blueprint
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from api.authentication.validation import (
    validate_integer_field,
    validate_json_request,
    validate_optional_string_field,
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
from services.device import device as device_service
from services.errors import ServiceError
from services.security.rate_limits import READ, WRITE

device_management_bp = Blueprint("device_management", __name__)

# Fields an administrator may set when registering a device. ``device_id``
# is required on creation but can never be changed afterwards.
_DEVICE_CREATE_FIELDS = {"device_id", "device_code", "device_name", "room_id"}

# Fields an administrator may update. ``registration_status`` is constrained to
# the lifecycle values the management API owns; activation to REGISTERED stays
# with the device-key provisioning CLI so devices are never left without a key.
_DEVICE_UPDATE_FIELDS = {"device_code", "device_name", "room_id", "registration_status"}

_REGISTRATION_STATUSES = {"PENDING", "DEACTIVATED"}


def _validate_device_create():
    data, error = validate_json_request(("device_id", "device_code", "room_id"))
    if error:
        return None, error

    unsupported = set(data) - _DEVICE_CREATE_FIELDS
    if unsupported:
        return None, error_response(
            "Unsupported fields", 400, fields=sorted(unsupported)
        )

    for field in ("device_id", "device_code"):
        data[field], error = validate_string_field(data, field)
        if error:
            return None, error

    if len(data["device_id"]) > 20:
        return None, error_response("device_id must not exceed 20 characters", 400)
    if len(data["device_code"]) > 50:
        return None, error_response("device_code must not exceed 50 characters", 400)

    device_name, error = validate_optional_string_field(
        data, "device_name", 50, allow_empty=True
    )
    if error:
        return None, error
    data["device_name"] = device_name

    room_id, error = validate_integer_field(data, "room_id")
    if error:
        return None, error
    data["room_id"] = room_id

    return data, None


def _validate_device_update(*, required_fields=()):
    data, error = validate_json_request(required_fields)
    if error:
        return None, error

    unsupported = set(data) - _DEVICE_UPDATE_FIELDS
    if unsupported:
        return None, error_response(
            "Unsupported fields", 400, fields=sorted(unsupported)
        )
    if not data:
        return None, error_response("At least one field is required", 400)

    if "device_code" in data:
        data["device_code"], error = validate_string_field(data, "device_code")
        if error:
            return None, error
        if len(data["device_code"]) > 50:
            return None, error_response(
                "device_code must not exceed 50 characters", 400
            )

    if "device_name" in data:
        device_name, error = validate_optional_string_field(
            data, "device_name", 50, allow_empty=True
        )
        if error:
            return None, error
        data["device_name"] = device_name

    if "room_id" in data:
        room_id, error = validate_integer_field(data, "room_id")
        if error:
            return None, error
        data["room_id"] = room_id

    if "registration_status" in data:
        status = data["registration_status"]
        if not isinstance(status, str) or not status.strip():
            return None, error_response(
                "registration_status must be a non-empty string", 400
            )
        status = status.strip().upper()
        if status not in _REGISTRATION_STATUSES:
            return None, error_response(
                "Invalid registration_status",
                400,
                allowed_values=sorted(_REGISTRATION_STATUSES),
            )
        data["registration_status"] = status

    return data, None


@device_management_bp.get("/devices")
@limiter.limit(READ)
@admin_required
def get_devices():
    """List all room devices, including deactivated devices.
    ---
    tags:
      - Device Management
    security:
      - Bearer: []
    responses:
      200:
        description: Devices ordered by device identifier
        schema:
          type: array
          items:
            type: object
            properties:
              device_id:
                type: string
              room_id:
                type: integer
              device_code:
                type: string
              device_name:
                type: string
                x-nullable: true
              registration_status:
                type: string
                enum: [PENDING, REGISTERED, DEACTIVATED]
              registered_at:
                type: string
                format: date-time
                x-nullable: true
              room:
                type: object
                x-nullable: true
                properties:
                  room_id:
                    type: integer
                  room_number:
                    type: string
                  room_name:
                    type: string
                  is_active:
                    type: boolean
      401:
        description: Authentication required
      403:
        description: Administrator access required
      500:
        description: Failed to load devices
    """
    try:
        devices = device_service.list_devices()
        return success_response([device.to_dict() for device in devices])
    except SQLAlchemyError as error:
        return database_error_response("device.list", error)


@device_management_bp.get("/devices/available-rooms")
@limiter.limit(READ)
@admin_required
def get_available_rooms():
    """List active rooms eligible for device assignment (no device assigned).
    ---
    tags:
      - Device Management
    security:
      - Bearer: []
    responses:
      200:
        description: Active rooms without an assigned device, ordered by room number
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
        description: Failed to load available rooms
    """
    try:
        rooms = device_service.list_available_rooms()
        return success_response([room.to_dict() for room in rooms])
    except SQLAlchemyError as error:
        return database_error_response("device.available_rooms", error)


@device_management_bp.get("/devices/<device_id>")
@limiter.limit(READ)
@admin_required
def get_device(device_id):
    """Get one room device by its identifier.
    ---
    tags:
      - Device Management
    security:
      - Bearer: []
    parameters:
      - in: path
        name: device_id
        type: string
        required: true
    responses:
      200:
        description: Device details
      401:
        description: Authentication required
      403:
        description: Administrator access required
      404:
        description: Device not found
    """
    try:
        device = device_service.get_device(device_id)
        if device is None:
            return error_response("Device not found", 404)
        return success_response(device.to_dict())
    except SQLAlchemyError as error:
        return database_error_response("device.get", error)


@device_management_bp.post("/devices")
@limiter.limit(WRITE)
@admin_required
def create_device():
    """Register a room device. New devices begin as PENDING.
    ---
    tags:
      - Device Management
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
          required: [device_id, device_code, room_id]
          properties:
            device_id:
              type: string
              maxLength: 20
              example: DEV001
            device_code:
              type: string
              maxLength: 50
              example: ESP32-001
            device_name:
              type: string
              maxLength: 50
              example: Room 101 Sensor
            room_id:
              type: integer
              example: 1
    responses:
      201:
        description: Device registered; activation is performed via the device-key CLI
      400:
        description: Invalid input
      401:
        description: Authentication required
      403:
        description: Administrator access required
      404:
        description: Referenced room not found
      409:
        description: Device identifier or code already exists, or the room is inactive or already assigned
    """
    data, error = _validate_device_create()
    if error:
        return error

    try:
        device = device_service.create_device(data)
    except ServiceError as error:
        return service_error_response(error)
    except IntegrityError as error:
        return database_error_response(
            "device.create", error, conflict_message="Device already exists"
        )
    except SQLAlchemyError as error:
        return database_error_response("device.create", error)

    return success_response(device.to_dict(), 201)


def _update_device(device_id, *, partial):
    try:
        device = device_service.get_device(device_id)
    except SQLAlchemyError as error:
        return database_error_response("device.get", error)
    if device is None:
        return error_response("Device not found", 404)

    required = () if partial else ("device_code", "room_id")
    data, error = _validate_device_update(required_fields=required)
    if error:
        return error

    try:
        device = device_service.update_device(device, data)
    except ServiceError as error:
        return service_error_response(error)
    except IntegrityError as error:
        return database_error_response(
            "device.update", error, conflict_message="Device code already exists"
        )
    except SQLAlchemyError as error:
        return database_error_response("device.update", error)

    return success_response(device.to_dict())


@device_management_bp.put("/devices/<device_id>")
@limiter.limit(WRITE)
@admin_required
def replace_device(device_id):
    """Replace the editable device fields.
    ---
    tags:
      - Device Management
    security:
      - Bearer: []
    consumes:
      - application/json
    parameters:
      - in: path
        name: device_id
        type: string
        required: true
      - in: body
        name: body
        required: true
        schema:
          type: object
          required: [device_code, room_id]
          properties:
            device_code:
              type: string
              maxLength: 50
            device_name:
              type: string
              maxLength: 50
            room_id:
              type: integer
            registration_status:
              type: string
              enum: [PENDING, DEACTIVATED]
    responses:
      200:
        description: Device updated
      400:
        description: Invalid input
      404:
        description: Device or referenced room not found
      409:
        description: Device code already exists, or the room is inactive or already assigned
    """
    return _update_device(device_id, partial=False)


@device_management_bp.patch("/devices/<device_id>")
@limiter.limit(WRITE)
@admin_required
def patch_device(device_id):
    """Update selected editable device fields.
    ---
    tags:
      - Device Management
    security:
      - Bearer: []
    consumes:
      - application/json
    parameters:
      - in: path
        name: device_id
        type: string
        required: true
      - in: body
        name: body
        required: true
        schema:
          type: object
          properties:
            device_code:
              type: string
              maxLength: 50
            device_name:
              type: string
              maxLength: 50
            room_id:
              type: integer
            registration_status:
              type: string
              enum: [PENDING, DEACTIVATED]
    responses:
      200:
        description: Device updated
      400:
        description: Invalid input
      404:
        description: Device or referenced room not found
      409:
        description: Device code already exists, or the room is inactive or already assigned
    """
    return _update_device(device_id, partial=True)


@device_management_bp.delete("/devices/<device_id>")
@limiter.limit(WRITE)
@admin_required
def delete_device(device_id):
    """Deactivate a room device while preserving occupancy and assistance history.
    ---
    tags:
      - Device Management
    security:
      - Bearer: []
    parameters:
      - in: path
        name: device_id
        type: string
        required: true
    responses:
      200:
        description: Device deactivated; its history is preserved
        schema:
          type: object
          properties:
            message:
              type: string
              example: Device deactivated
            device_id:
              type: string
      401:
        description: Authentication required
      403:
        description: Administrator access required
      404:
        description: Device not found
    """
    try:
        device = device_service.get_device(device_id)
        if device is None:
            return error_response("Device not found", 404)
        device_service.deactivate_device(device)
        return success_response(
            {"message": "Device deactivated", "device_id": device_id}
        )
    except SQLAlchemyError as error:
        return database_error_response("device.deactivate", error)
