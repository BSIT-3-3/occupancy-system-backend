from datetime import datetime, timezone
from functools import wraps

from flask import Blueprint, jsonify, request
from sqlalchemy import CheckConstraint

from database.extensions import db
from models.room import Room  # Adjust to your actual Room model import.

emergency_bp = Blueprint("emergency_broadcast", __name__, url_prefix="/api")


# Replace these development placeholders with your real authentication
# decorators before deployment.
def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        # TODO: Verify authenticated user has the Admin role.
        return fn(*args, **kwargs)
    return wrapper


def gateway_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        # TODO: Authenticate the Central LoRa Gateway.
        return fn(*args, **kwargs)
    return wrapper


class EmergencyBroadcast(db.Model):
    __tablename__ = "emergency_broadcast"

    broadcast_id = db.Column(db.Integer, primary_key=True)
    message_text = db.Column(db.String(500), nullable=False)
    created_by = db.Column(db.Integer, nullable=False)
    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    targets = db.relationship(
        "EmergencyBroadcastTarget",
        back_populates="broadcast",
        cascade="all, delete-orphan",
    )


class EmergencyBroadcastTarget(db.Model):
    __tablename__ = "emergency_broadcast_target"

    target_id = db.Column(db.Integer, primary_key=True)
    broadcast_id = db.Column(
        db.Integer,
        db.ForeignKey("emergency_broadcast.broadcast_id"),
        nullable=False,
        index=True,
    )
    room_id = db.Column(
        db.Integer,
        db.ForeignKey("room.room_id"),
        nullable=False,
        index=True,
    )
    delivery_status = db.Column(
        db.String(20), nullable=False, default="PENDING"
    )
    dispatched_at = db.Column(db.DateTime(timezone=True))
    acknowledged_at = db.Column(db.DateTime(timezone=True))
    failure_reason = db.Column(db.String(250))

    broadcast = db.relationship(
        "EmergencyBroadcast", back_populates="targets"
    )
    room = db.relationship("Room")

    __table_args__ = (
        db.UniqueConstraint(
            "broadcast_id", "room_id", name="uq_broadcast_target_room"
        ),
        CheckConstraint(
            "delivery_status IN "
            "('PENDING', 'DISPATCHED', 'ACKNOWLEDGED', 'FAILED')",
            name="ck_broadcast_target_status",
        ),
    )


def error(message, code):
    return jsonify({"success": False, "error": message}), code


def serialize_target(target, include_message=True):
    result = {
        "target_id": target.target_id,
        "room_id": target.room_id,
        "room_number": target.room.room_number,
        "room_name": target.room.room_name,
        "delivery_status": target.delivery_status,
        "dispatched_at": (
            target.dispatched_at.isoformat() if target.dispatched_at else None
        ),
        "acknowledged_at": (
            target.acknowledged_at.isoformat()
            if target.acknowledged_at else None
        ),
        "failure_reason": target.failure_reason,
    }
    if include_message:
        result["broadcast_id"] = target.broadcast_id
        result["message_text"] = target.broadcast.message_text
    return result


# Desktop: POST /api/admin/emergency-broadcasts
# JSON: {"message_text": "...", "target_room_ids": [1, 2]}
@emergency_bp.route("/admin/emergency-broadcasts", methods=["POST"])
@admin_required
def create_broadcast():
    if not request.is_json:
        return error("Content-Type must be application/json.", 415)

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return error("Request body must be a JSON object.", 400)

    message = data.get("message_text")
    room_ids = data.get("target_room_ids")

    if not isinstance(message, str) or not message.strip():
        return error("message_text is required.", 400)
    message = message.strip()
    if len(message) > 500:
        return error("message_text cannot exceed 500 characters.", 400)

    if (
        not isinstance(room_ids, list)
        or not room_ids
        or any(type(room_id) is not int for room_id in room_ids)
    ):
        return error(
            "target_room_ids must be a non-empty list of integer room IDs.",
            400,
        )

    room_ids = list(dict.fromkeys(room_ids))
    rooms = Room.query.filter(
        Room.room_id.in_(room_ids),
        Room.is_active.is_(True),
    ).all()
    room_map = {room.room_id: room for room in rooms}
    invalid_ids = [room_id for room_id in room_ids if room_id not in room_map]
    if invalid_ids:
        return jsonify({
            "success": False,
            "error": "One or more target rooms do not exist or are inactive.",
            "invalid_room_ids": invalid_ids,
        }), 400

    # Replace this with the ID from your authenticated administrator session.
    # This header is only a temporary integration placeholder, not auth.
    try:
        created_by = int(request.headers.get("X-Admin-User-ID", ""))
    except (TypeError, ValueError):
        return error("Authenticated administrator ID is unavailable.", 401)

    try:
        broadcast = EmergencyBroadcast(
            message_text=message,
            created_by=created_by,
        )
        db.session.add(broadcast)
        db.session.flush()

        for room in rooms:
            db.session.add(EmergencyBroadcastTarget(
                broadcast_id=broadcast.broadcast_id,
                room_id=room.room_id,
                delivery_status="PENDING",
            ))

        db.session.commit()
        return jsonify({
            "success": True,
            "message": "Emergency broadcast created.",
            "broadcast_id": broadcast.broadcast_id,
            "targets": [serialize_target(t) for t in broadcast.targets],
        }), 201
    except Exception:
        db.session.rollback()
        raise


# Gateway: GET /api/gateway/emergency-broadcasts/pending
# Returns each pending message with its target room identity, then marks it
# DISPATCHED when handed to the Gateway.
@emergency_bp.route("/gateway/emergency-broadcasts/pending", methods=["GET"])
@gateway_required
def get_pending_broadcasts():
    try:
        targets = (
            EmergencyBroadcastTarget.query
            .join(EmergencyBroadcast)
            .join(Room)
            .filter(
                EmergencyBroadcastTarget.delivery_status == "PENDING",
                Room.is_active.is_(True),
            )
            .order_by(
                EmergencyBroadcast.created_at.asc(),
                EmergencyBroadcastTarget.target_id.asc(),
            )
            .all()
        )

        items = []
        for target in targets:
            target.delivery_status = "DISPATCHED"
            target.dispatched_at = datetime.now(timezone.utc)
            items.append(serialize_target(target))

        db.session.commit()
        return jsonify({
            "success": True,
            "count": len(items),
            "items": items,
        }), 200
    except Exception:
        db.session.rollback()
        raise


# Gateway: PATCH /api/gateway/emergency-broadcast-targets/<target_id>/status
# ACK body: {"delivery_status": "ACKNOWLEDGED"}
# Failure body: {"delivery_status": "FAILED", "failure_reason": "..."}
@emergency_bp.route(
    "/gateway/emergency-broadcast-targets/<int:target_id>/status",
    methods=["PATCH"],
)
@gateway_required
def update_target_status(target_id):
    if not request.is_json:
        return error("Content-Type must be application/json.", 415)

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return error("Request body must be a JSON object.", 400)

    status = data.get("delivery_status")
    reason = data.get("failure_reason")

    if status not in {"ACKNOWLEDGED", "FAILED"}:
        return error(
            "delivery_status must be ACKNOWLEDGED or FAILED.", 400
        )
    if status == "FAILED":
        if not isinstance(reason, str) or not reason.strip():
            return error("failure_reason is required for FAILED.", 400)
        reason = reason.strip()[:250]

    target = db.session.get(EmergencyBroadcastTarget, target_id)
    if target is None:
        return error("Broadcast target not found.", 404)
    if target.delivery_status != "DISPATCHED":
        return error("Only DISPATCHED targets can be updated.", 409)

    target.delivery_status = status
    if status == "ACKNOWLEDGED":
        target.acknowledged_at = datetime.now(timezone.utc)
        target.failure_reason = None
    else:
        target.failure_reason = reason

    try:
        db.session.commit()
        return jsonify({
            "success": True,
            "target": serialize_target(target),
        }), 200
    except Exception:
        db.session.rollback()
        raise


# Desktop: GET /api/admin/emergency-broadcasts/<broadcast_id>
@emergency_bp.route(
    "/admin/emergency-broadcasts/<int:broadcast_id>", methods=["GET"]
)
@admin_required
def get_broadcast_status(broadcast_id):
    broadcast = db.session.get(EmergencyBroadcast, broadcast_id)
    if broadcast is None:
        return error("Emergency broadcast not found.", 404)

    return jsonify({
        "success": True,
        "broadcast": {
            "broadcast_id": broadcast.broadcast_id,
            "message_text": broadcast.message_text,
            "created_by": broadcast.created_by,
            "created_at": broadcast.created_at.isoformat(),
            "targets": [
                serialize_target(target, include_message=False)
                for target in broadcast.targets
            ],
        },
    }), 200
