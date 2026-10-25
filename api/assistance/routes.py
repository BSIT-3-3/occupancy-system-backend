
from flask import Blueprint, request, jsonify
from sqlalchemy.exc import SQLAlchemyError

from database.extensions import db
from database.models.assistance_request import AssistanceRequest
from database.models.room import Room
from database.models.room_device import RoomDevice

assistance_bp = Blueprint("assistance", __name__)


def request_to_dict(item):
    return {
        "assistance_request_id": item.assistance_request_id,
        "room_id": item.room_id,
        "device_id": item.device_id,
        "status": item.status,
        "requested_at": (
            item.requested_at.isoformat()
            if item.requested_at else None
        ),
        "acknowledged_at": (
            item.acknowledged_at.isoformat()
            if item.acknowledged_at else None
        ),
        "resolved_at": (
            item.resolved_at.isoformat()
            if item.resolved_at else None
        ),
        "remarks": item.remarks,
    }


# CREATE: Receive a new assistance request
@assistance_bp.post("/assistance-requests")
def create_assistance_request():
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({"error": "A JSON object is required"}), 400

    room_id = data.get("room_id")
    device_id = data.get("device_id")

    if room_id is None or not isinstance(device_id, str) or not device_id.strip():
        return jsonify({
            "error": "room_id and device_id are required"
        }), 400

    try:
        room_id = int(room_id)
    except (TypeError, ValueError):
        return jsonify({"error": "room_id must be an integer"}), 400

    try:
        room = db.session.get(Room, room_id)
        device = db.session.get(RoomDevice, device_id.strip())

        if room is None:
            return jsonify({"error": "Room not found"}), 400

        if device is None:
            return jsonify({"error": "Device not found"}), 400

        if device.room_id != room.room_id:
            return jsonify({
                "error": "The device does not belong to this room"
            }), 400

        item = AssistanceRequest(
            room_id=room.room_id,
            device_id=device.device_id,
            status="PENDING",
            remarks=data.get("remarks"),
        )

        db.session.add(item)
        db.session.commit()

        return jsonify(request_to_dict(item)), 201

    except SQLAlchemyError:
        db.session.rollback()
        return jsonify({"error": "Database operation failed"}), 500


# READ ALL: Retrieve assistance requests
@assistance_bp.get("/assistance-requests")
def get_assistance_requests():
    try:
        items = (
            AssistanceRequest.query
            .order_by(AssistanceRequest.requested_at.desc())
            .all()
        )
        return jsonify([request_to_dict(item) for item in items]), 200

    except SQLAlchemyError:
        return jsonify({"error": "Database operation failed"}), 500


# READ ONE: Retrieve a specific request
@assistance_bp.get("/assistance-requests/<int:request_id>")
def get_assistance_request(request_id):
    try:
        item = db.session.get(AssistanceRequest, request_id)

        if item is None:
            return jsonify({"error": "Assistance request not found"}), 404

        return jsonify(request_to_dict(item)), 200

    except SQLAlchemyError:
        return jsonify({"error": "Database operation failed"}), 500


# UPDATE: Update request status, timestamps, or remarks
@assistance_bp.put("/assistance-requests/<int:request_id>")
def update_assistance_request(request_id):
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({"error": "A JSON object is required"}), 400

    allowed_fields = {"status", "acknowledged_at", "resolved_at", "remarks"}
    unknown_fields = set(data.keys()) - allowed_fields

    if unknown_fields:
        return jsonify({
            "error": "Unsupported fields",
            "fields": sorted(unknown_fields),
        }), 400

    if not data:
        return jsonify({"error": "At least one field is required"}), 400

    if "status" in data:
        if not isinstance(data["status"], str) or not data["status"].strip():
            return jsonify({"error": "status must be a non-empty string"}), 400

    if "remarks" in data:
        if data["remarks"] is not None and not isinstance(data["remarks"], str):
            return jsonify({"error": "remarks must be a string or null"}), 400

    try:
        item = db.session.get(AssistanceRequest, request_id)

        if item is None:
            return jsonify({"error": "Assistance request not found"}), 404

        for field in ("status", "remarks"):
            if field in data:
                value = data[field]
                setattr(item, field, value.strip() if field == "status" else value)

        # Timestamps accept ISO 8601 strings or null.
        for field in ("acknowledged_at", "resolved_at"):
            if field in data:
                value = data[field]

                if value is None:
                    setattr(item, field, None)
                    continue

                if not isinstance(value, str):
                    db.session.rollback()
                    return jsonify({
                        "error": f"{field} must be an ISO 8601 string or null"
                    }), 400

                from datetime import datetime

                try:
                    setattr(item, field, datetime.fromisoformat(
                        value.replace("Z", "+00:00")
                    ))
                except ValueError:
                    db.session.rollback()
                    return jsonify({
                        "error": f"{field} must be a valid ISO 8601 timestamp"
                    }), 400

        db.session.commit()
        return jsonify(request_to_dict(item)), 200

    except SQLAlchemyError:
        db.session.rollback()
        return jsonify({"error": "Database operation failed"}), 500
