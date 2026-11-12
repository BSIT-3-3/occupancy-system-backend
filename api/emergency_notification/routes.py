from flask import Blueprint, request
from flask_jwt_extended import get_jwt_identity
from sqlalchemy.exc import SQLAlchemyError

from api.authentication.validation import validate_json_request, validate_string_field
from api.responses import (
    database_error_response,
    error_response,
    service_error_response,
    success_response,
)
from api.security import admin_required
from database.extensions import db, limiter
from database.models.emergency_broadcast import EmergencyBroadcast
from services.emergency_notification.broadcast import (
    create_broadcast,
    record_acknowledgment,
)
from services.errors import ServiceError
from services.security.device_auth import authenticate_device
from services.security.rate_limits import DEVICE, WRITE, device_key_func

emergency_broadcast_bp = Blueprint(
    "emergency_broadcast", __name__, url_prefix="/api/admin"
)
emergency_broadcast_gateway_bp = Blueprint(
    "emergency_broadcast_gateway", __name__, url_prefix="/api/gateway"
)


@emergency_broadcast_bp.post("/emergency-broadcasts")
@limiter.limit(WRITE)
@admin_required
def create_emergency_broadcast():
    """Create an emergency broadcast for selected rooms.
    ---
    tags:
      - Emergency Broadcast
    security:
      - Bearer: []
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required: [message_text, target_room_ids]
          properties:
            message_text:
              type: string
              maxLength: 500
            target_room_ids:
              type: array
              minItems: 1
              items:
                type: integer
    responses:
      201:
        description: Broadcast and target records created
      400:
        description: Invalid message or room selection
      401:
        description: Authentication required
      403:
        description: Administrator access required
    """
    data, error = validate_json_request(["message_text", "target_room_ids"])
    if error:
        return error

    unsupported = set(data) - {"message_text", "target_room_ids"}
    if unsupported:
        return error_response("Unsupported fields", 400, fields=sorted(unsupported))

    message_text, error = validate_string_field(data, "message_text")
    if error:
        return error
    if len(message_text) > 500:
        return error_response("message_text must not exceed 500 characters", 400)

    room_ids = data["target_room_ids"]
    if (
        not isinstance(room_ids, list)
        or not room_ids
        or any(type(room_id) is not int or room_id <= 0 for room_id in room_ids)
    ):
        return error_response(
            "target_room_ids must be a non-empty list of room IDs", 400
        )

    try:
        broadcast = create_broadcast(
            message_text=message_text,
            target_room_ids=room_ids,
            created_by=int(get_jwt_identity()),
        )
    except ServiceError as error:
        return service_error_response(error)
    except SQLAlchemyError as error:
        return database_error_response("emergency_broadcast.create", error)

    return success_response(
        {
            "broadcast_id": broadcast.broadcast_id,
            "message_text": broadcast.message_text,
            "targets": [
                {
                    "target_id": target.target_id,
                    "room_id": target.room_id,
                    "delivery_status": target.delivery_status,
                }
                for target in broadcast.targets
            ],
        },
        201,
    )


@emergency_broadcast_gateway_bp.post(
    "/emergency-broadcasts/<int:broadcast_id>/acknowledgments"
)
@limiter.limit(DEVICE, key_func=device_key_func)
def acknowledge_emergency_broadcast(broadcast_id):
    """Record a Room Node's confirmed receipt, forwarded by the Gateway.
    ---
    tags:
      - Emergency Broadcast
    parameters:
      - in: path
        name: broadcast_id
        type: integer
        required: true
      - in: header
        name: X-Device-Key
        type: string
        required: true
        description: Credential for the Room Node that confirmed receipt
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
    responses:
      200:
        description: Target acknowledged, including safe retries
      400:
        description: Invalid request body
      401:
        description: Invalid device credentials
      403:
        description: Device is not registered
      404:
        description: Broadcast or target room not found
      409:
        description: Target has failed
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
        device = authenticate_device(
            device_id, request.headers.get("X-Device-Key"), lock=True
        )
        target = record_acknowledgment(
            broadcast_id=broadcast_id,
            room_id=device.room_id,
            allowed_prior_statuses={"PENDING", "DISPATCHED"},
        )
        if target is None:
            if db.session.get(EmergencyBroadcast, broadcast_id) is None:
                return error_response("Emergency broadcast not found", 404)
            return error_response("Broadcast target not found", 404)
        if target.delivery_status == "FAILED":
            return error_response("Broadcast target has failed", 409)
    except ServiceError as error:
        return service_error_response(error)
    except SQLAlchemyError as error:
        return database_error_response("emergency_broadcast.acknowledge", error)

    return success_response(
        {
            "broadcast_id": target.broadcast_id,
            "room_id": target.room_id,
            "device_id": device.device_id,
            "delivery_status": target.delivery_status,
            "acknowledged_at": target.acknowledged_at.isoformat(),
        }
    )
