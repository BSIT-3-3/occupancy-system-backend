from flask import Blueprint, request
from sqlalchemy.exc import SQLAlchemyError

from api.authentication.validation import validate_json_request, validate_string_field
from api.responses import (
    database_error_response,
    error_response,
    service_error_response,
    success_response,
)
from api.security import admin_required
from database.extensions import limiter
from services.device.heartbeat import record_heartbeat
from services.device.monitoring import (
    get_device_status,
    get_device_summary,
    list_device_status_history,
    list_device_statuses,
    serialize_device_status,
    serialize_status_history,
)
from services.errors import ServiceError
from services.security.rate_limits import DEVICE, READ, device_key_func

device_monitoring_bp = Blueprint(
    "device_monitoring", __name__, url_prefix="/api/device-monitoring"
)


@device_monitoring_bp.post("/heartbeat")
@limiter.limit(DEVICE, key_func=device_key_func)
def receive_heartbeat():
    """Accept a heartbeat from a registered Room Node.
    ---
    tags:
      - Device Monitoring
    consumes:
      - application/json
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required: [device_id]
          properties:
            device_id:
              type: string
              maxLength: 20
              example: DEV001
      - in: header
        name: X-Device-Key
        type: string
        required: true
        description: Per-device credential provisioned by an operator
    responses:
      200:
        description: Heartbeat accepted; current status is ONLINE
        schema:
          type: object
          properties:
            device_id:
              type: string
            current_status:
              type: string
              enum: [ONLINE]
            last_communication_at:
              type: string
              format: date-time
      400:
        description: Invalid request body
      401:
        description: Device credentials are invalid
      403:
        description: Device is not registered or its room is inactive
      500:
        description: Heartbeat could not be recorded
    """
    data, error = validate_json_request(("device_id",))
    if error:
        return error

    unsupported = set(data) - {"device_id"}
    if unsupported:
        return error_response("Unsupported fields", 400, fields=sorted(unsupported))

    device_id, error = validate_string_field(data, "device_id")
    if error:
        return error
    if len(device_id) > 20:
        return error_response("device_id must not exceed 20 characters", 400)

    try:
        device = record_heartbeat(device_id, request.headers.get("X-Device-Key"))
    except ServiceError as error:
        return service_error_response(error)
    except SQLAlchemyError as error:
        return database_error_response("device.heartbeat", error)

    return success_response(
        {
            "message": "Heartbeat received",
            "device_id": device.device_id,
            "current_status": device.current_status,
            "last_communication_at": device.last_communication_at.isoformat(),
        }
    )


@device_monitoring_bp.get("/summary")
@limiter.limit(READ)
@admin_required
def get_device_monitoring_summary():
    """Get registered device availability counts for the dashboard.
    ---
    tags:
      - Device Monitoring
    security:
      - Bearer: []
    responses:
      200:
        description: Registered devices assigned to active rooms, by availability
        schema:
          type: object
          properties:
            registered_count:
              type: integer
              description: Registered devices, including those assigned to inactive rooms
            active_count:
              type: integer
              description: Registered devices assigned to active rooms
            online_count:
              type: integer
            offline_count:
              type: integer
            unknown_count:
              type: integer
      401:
        description: Authentication required
      403:
        description: Administrator access required
    """
    try:
        return success_response(get_device_summary())
    except SQLAlchemyError as error:
        return database_error_response("device_monitoring.summary", error)


@device_monitoring_bp.get("/devices/status")
@limiter.limit(READ)
@admin_required
def get_all_device_statuses():
    """Get availability and last communication for all registered devices.
    ---
    tags:
      - Device Monitoring
    security:
      - Bearer: []
    responses:
      200:
        description: Device status list
      401:
        description: Authentication required
      403:
        description: Administrator access required
    """
    try:
        devices = list_device_statuses()
        return success_response([serialize_device_status(device) for device in devices])
    except SQLAlchemyError as error:
        return database_error_response("device_monitoring.status.list", error)


@device_monitoring_bp.get("/devices/<device_id>/status")
@limiter.limit(READ)
@admin_required
def get_one_device_status(device_id):
    """Get current availability for one device.
    ---
    tags:
      - Device Monitoring
    security:
      - Bearer: []
    parameters:
      - in: path
        name: device_id
        type: string
        required: true
    responses:
      200:
        description: Current device status
      401:
        description: Authentication required
      403:
        description: Administrator access required
      404:
        description: Device not found
    """
    try:
        device = get_device_status(device_id)
        if device is None:
            return error_response("Device not found", 404)
        return success_response(serialize_device_status(device))
    except SQLAlchemyError as error:
        return database_error_response("device_monitoring.status.get", error)


@device_monitoring_bp.get("/devices/<device_id>/history")
@limiter.limit(READ)
@admin_required
def get_one_device_status_history(device_id):
    """Get recent status transitions for one device.
    ---
    tags:
      - Device Monitoring
    security:
      - Bearer: []
    parameters:
      - in: path
        name: device_id
        type: string
        required: true
      - in: query
        name: limit
        type: integer
        default: 100
        minimum: 1
        maximum: 500
    responses:
      200:
        description: Status transitions, newest first
      400:
        description: Invalid limit
      401:
        description: Authentication required
      403:
        description: Administrator access required
      404:
        description: Device not found
    """
    raw_limit = request.args.get("limit", "100")
    try:
        limit = int(raw_limit)
    except ValueError:
        return error_response("limit must be an integer between 1 and 500", 400)
    if not 1 <= limit <= 500:
        return error_response("limit must be an integer between 1 and 500", 400)

    try:
        if get_device_status(device_id) is None:
            return error_response("Device not found", 404)
        history = list_device_status_history(device_id, limit=limit)
        return success_response([serialize_status_history(entry) for entry in history])
    except SQLAlchemyError as error:
        return database_error_response("device_monitoring.history.list", error)
