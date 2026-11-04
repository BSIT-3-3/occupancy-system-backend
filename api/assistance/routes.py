from datetime import UTC, datetime

from flask import Blueprint, jsonify, request
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
        "requested_at": (item.requested_at.isoformat() if item.requested_at else None),
        "acknowledged_at": (
            item.acknowledged_at.isoformat() if item.acknowledged_at else None
        ),
        "resolved_at": (item.resolved_at.isoformat() if item.resolved_at else None),
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
        return jsonify({"error": "room_id and device_id are required"}), 400

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
            return jsonify({"error": "The device does not belong to this room"}), 400

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
        items = AssistanceRequest.query.order_by(
            AssistanceRequest.requested_at.desc()
        ).all()
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


# UPDATE: Move an assistance request through its workflow
@assistance_bp.put("/assistance-requests/<int:request_id>")
def update_assistance_request(request_id):
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({"error": "A JSON object is required"}), 400

    allowed_fields = {"status", "remarks"}
    unknown_fields = set(data.keys()) - allowed_fields

    if unknown_fields:
        return jsonify(
            {
                "error": "Unsupported fields",
                "fields": sorted(unknown_fields),
            }
        ), 400

    if not data:
        return jsonify({"error": "At least one field is required"}), 400

    if "status" in data and (
        not isinstance(data["status"], str) or not data["status"].strip()
    ):
        return jsonify({"error": "status must be a non-empty string"}), 400

    if "remarks" in data and (
        data["remarks"] is not None and not isinstance(data["remarks"], str)
    ):
        return jsonify({"error": "remarks must be a string or null"}), 400

    try:
        item = db.session.get(AssistanceRequest, request_id)

        if item is None:
            return jsonify({"error": "Assistance request not found"}), 404

        if "status" in data:
            new_status = data["status"].strip().upper()
            current_status = item.status.upper()

            allowed_transitions = {
                "PENDING": "ACKNOWLEDGED",
                "ACKNOWLEDGED": "RESOLVED",
            }

            if new_status != current_status:
                expected_status = allowed_transitions.get(current_status)

                if new_status != expected_status:
                    return jsonify(
                        {
                            "error": "Invalid status transition",
                            "current_status": current_status,
                            "requested_status": new_status,
                        }
                    ), 400

                now = datetime.now(UTC)

                if new_status == "ACKNOWLEDGED":
                    item.acknowledged_at = now

                elif new_status == "RESOLVED":
                    item.resolved_at = now

                item.status = new_status

        if "remarks" in data:
            item.remarks = data["remarks"]

        db.session.commit()

        return jsonify(request_to_dict(item)), 200

    except SQLAlchemyError:
        db.session.rollback()
        return jsonify({"error": "Database operation failed"}), 500
