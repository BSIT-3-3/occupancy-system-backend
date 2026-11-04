from flask import Blueprint, current_app, jsonify
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from werkzeug.security import generate_password_hash

from api.authentication.validation import (
    validate_integer_field,
    validate_json_request,
    validate_optional_string_field,
    validate_string_field,
)
from database import db
from database.models.profile import UserProfile
from database.models.role import Role
from database.models.user import User

users_bp = Blueprint("users", __name__)


def username_taken(username, exclude_id=None):
    query = db.session.query(User).filter(User.username == username)

    if exclude_id is not None:
        query = query.filter(User.user_id != exclude_id)

    return query.first() is not None


DEFAULT_REGISTRATION_ROLE = "USER"


def register_user(data):
    try:
        existing_user = User.query.filter_by(username=data["username"]).first()
        if existing_user:
            return None, "Username already exists", 409

        role = Role.query.filter_by(role_name=DEFAULT_REGISTRATION_ROLE).first()
        if not role:
            return None, "Default registration role is not configured", 500

        full_name = " ".join(
            filter(None, [data["first_name"], data.get("middle_name"), data["last_name"]])
        )
        user = User(
            username=data["username"],
            password=generate_password_hash(data["password"]),
            full_name=full_name,
            role_id=role.role_id,
            status="ACTIVE",
        )
        db.session.add(user)
        db.session.flush()

        db.session.add(
            UserProfile(
                user_id=user.user_id,
                first_name=data["first_name"],
                middle_name=data.get("middle_name"),
                last_name=data["last_name"],
                contact_number=data.get("contact_number"),
            )
        )
        db.session.commit()

        return {
            "user_id": user.user_id,
            "username": user.username,
            "full_name": user.full_name,
            "status": user.status,
        }, None, 201
    except (KeyError, TypeError, ValueError, SQLAlchemyError):
        db.session.rollback()
        raise


def _database_failure(operation, error, *, conflict_message=None):
    db.session.rollback()
    if isinstance(error, IntegrityError) and conflict_message:
        return jsonify({"error": conflict_message}), 409
    current_app.logger.error(
        "Database operation %s failed (%s)", operation, type(error).__name__
    )
    return jsonify({"error": "Database operation failed"}), 500


def _validate_user_payload(*, creating):
    fields = ["username", "role_id"]
    if creating:
        fields.append("password")
    data, error = validate_json_request(fields)
    if error:
        return None, error

    data["username"], error = validate_string_field(data, "username")
    if error:
        return None, error
    if len(data["username"]) > 50:
        return None, (jsonify({"error": "username must not exceed 50 characters"}), 400)

    data["role_id"], error = validate_integer_field(data, "role_id")
    if error:
        return None, error

    if creating or "password" in data:
        password = data.get("password")
        if not isinstance(password, str) or (creating and not password):
            return None, (jsonify({"error": "password must be a non-empty string"}), 400)

    for field, max_length in (("full_name", 100), ("status", 20)):
        if field in data:
            value, error = validate_optional_string_field(data, field, max_length)
            if error:
                return None, error
            if field == "status" and value is None:
                return None, (jsonify({"error": "status must be a string"}), 400)
            data[field] = value

    return data, None


@users_bp.post("/users")
def create_user():
    data, error = _validate_user_payload(creating=True)
    if error:
        return error

    try:
        if not db.session.get(Role, data["role_id"]):
            return jsonify({"error": "role_id does not exist"}), 400
        if username_taken(data["username"]):
            return jsonify({"error": "Username already exists"}), 409

        user = User(
            username=data["username"],
            password=generate_password_hash(data["password"]),
            full_name=data.get("full_name"),
            role_id=data["role_id"],
            status=data.get("status", "active"),
        )
        db.session.add(user)
        db.session.commit()
        return jsonify(user.to_dict()), 201
    except IntegrityError as error:
        return _database_failure("user.create", error, conflict_message="Username already exists")
    except SQLAlchemyError as error:
        return _database_failure("user.create", error)
    except (AttributeError, TypeError, ValueError) as error:
        return _database_failure("user.create", error)


@users_bp.get("/users")
def get_users():
    try:
        users = db.session.query(User).all()
        return jsonify([user.to_dict() for user in users])
    except SQLAlchemyError as error:
        return _database_failure("user.list", error)
    except (AttributeError, TypeError, ValueError) as error:
        return _database_failure("user.list", error)


@users_bp.get("/users/<int:user_id>")
def get_user(user_id):
    try:
        user = db.session.get(User, user_id)
        if not user:
            return jsonify({"error": "User not found"}), 404
        return jsonify(user.to_dict())
    except SQLAlchemyError as error:
        return _database_failure("user.get", error)
    except (AttributeError, TypeError, ValueError) as error:
        return _database_failure("user.get", error)


@users_bp.put("/users/<int:user_id>")
def update_user(user_id):
    try:
        user = db.session.get(User, user_id)
        if not user:
            return jsonify({"error": "User not found"}), 404

        data, error = _validate_user_payload(creating=False)
        if error:
            return error
        if not db.session.get(Role, data["role_id"]):
            return jsonify({"error": "role_id does not exist"}), 400
        if username_taken(data["username"], exclude_id=user_id):
            return jsonify({"error": "Username already exists"}), 409

        user.username = data["username"]
        user.full_name = data.get("full_name")
        user.role_id = data["role_id"]
        user.status = data.get("status", "active")
        if data.get("password"):
            user.password = generate_password_hash(data["password"])

        db.session.commit()
        return jsonify(user.to_dict())
    except IntegrityError as error:
        return _database_failure("user.update", error, conflict_message="Username already exists")
    except SQLAlchemyError as error:
        return _database_failure("user.update", error)
    except (AttributeError, TypeError, ValueError) as error:
        return _database_failure("user.update", error)


@users_bp.delete("/users/<int:user_id>")
def delete_user(user_id):
    try:
        user = db.session.get(User, user_id)
        if not user:
            return jsonify({"error": "User not found"}), 404
        db.session.delete(user)
        db.session.commit()
        return jsonify({"message": "User deleted"}), 200
    except IntegrityError as error:
        return _database_failure("user.delete", error, conflict_message="User cannot be deleted")
    except SQLAlchemyError as error:
        return _database_failure("user.delete", error)
