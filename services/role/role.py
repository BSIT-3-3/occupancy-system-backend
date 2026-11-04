from flask import Blueprint, current_app, jsonify
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from api.authentication.validation import (
    validate_json_request,
    validate_optional_string_field,
    validate_string_field,
)
from database import db
from database.models.role import Role

roles_bp = Blueprint("roles", __name__)


def _validate_role_payload():
    data, error = validate_json_request(["role_name"])
    if error:
        return None, error

    data["role_name"], error = validate_string_field(data, "role_name")
    if error:
        return None, error
    if len(data["role_name"]) > 50:
        return None, (
            jsonify({"error": "role_name must not exceed 50 characters"}),
            400,
        )

    if "description" in data:
        data["description"], error = validate_optional_string_field(
            data, "description", 25
        )
        if error:
            return None, error
    return data, None


def _database_failure(operation, error, *, conflict_message=None):
    db.session.rollback()
    if isinstance(error, IntegrityError) and conflict_message:
        return jsonify({"error": conflict_message}), 409
    current_app.logger.error(
        "Database operation %s failed (%s)", operation, type(error).__name__
    )
    return jsonify({"error": "Database operation failed"}), 500


@roles_bp.post("/roles")
def create_role():
    data, error = _validate_role_payload()
    if error:
        return error
    try:
        role = Role(role_name=data["role_name"], description=data.get("description"))
        db.session.add(role)
        db.session.commit()
        return jsonify(role.to_dict()), 201
    except IntegrityError as error:
        return _database_failure(
            "role.create", error, conflict_message="Role already exists"
        )
    except SQLAlchemyError as error:
        return _database_failure("role.create", error)
    except (AttributeError, TypeError, ValueError) as error:
        return _database_failure("role.create", error)


@roles_bp.get("/roles")
def get_roles():
    try:
        roles = db.session.query(Role).all()
        return jsonify([role.to_dict() for role in roles])
    except SQLAlchemyError as error:
        return _database_failure("role.list", error)
    except (AttributeError, TypeError, ValueError) as error:
        return _database_failure("role.list", error)


@roles_bp.get("/roles/<int:role_id>")
def get_role(role_id):
    try:
        role = db.session.get(Role, role_id)
        if not role:
            return jsonify({"error": "Role not found"}), 404
        return jsonify(role.to_dict())
    except SQLAlchemyError as error:
        return _database_failure("role.get", error)
    except (AttributeError, TypeError, ValueError) as error:
        return _database_failure("role.get", error)


@roles_bp.put("/roles/<int:role_id>")
def update_role(role_id):
    try:
        role = db.session.get(Role, role_id)
        if not role:
            return jsonify({"error": "Role not found"}), 404
        data, error = _validate_role_payload()
        if error:
            return error

        role.role_name = data["role_name"]
        role.description = data.get("description")
        db.session.commit()
        return jsonify(role.to_dict())
    except IntegrityError as error:
        return _database_failure(
            "role.update", error, conflict_message="Role already exists"
        )
    except SQLAlchemyError as error:
        return _database_failure("role.update", error)
    except (AttributeError, TypeError, ValueError) as error:
        return _database_failure("role.update", error)


@roles_bp.delete("/roles/<int:role_id>")
def delete_role(role_id):
    try:
        role = db.session.get(Role, role_id)
        if not role:
            return jsonify({"error": "Role not found"}), 404
        db.session.delete(role)
        db.session.commit()
        return jsonify({"message": "Role deleted"}), 200
    except IntegrityError as error:
        return _database_failure(
            "role.delete", error, conflict_message="Role is assigned to users"
        )
    except SQLAlchemyError as error:
        return _database_failure("role.delete", error)
