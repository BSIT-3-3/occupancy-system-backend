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
    unexpected_error_response,
)
from api.security import admin_required
from services.authentication import user as user_service
from services.errors import ServiceError

users_bp = Blueprint("users", __name__)


def _validate_user_payload(*, creating):
    required = ["username", "role_id"]
    if creating:
        required.append("password")
    data, error = validate_json_request(required)
    if error:
        return None, error

    data["username"], error = validate_string_field(data, "username")
    if error:
        return None, error
    if len(data["username"]) > 50:
        return None, error_response("username must not exceed 50 characters", 400)

    data["role_id"], error = validate_integer_field(data, "role_id")
    if error:
        return None, error

    if creating or "password" in data:
        password = data.get("password")
        if not isinstance(password, str) or (creating and not password):
            return None, error_response("password must be a non-empty string", 400)
        if password and len(password) < 12:
            return None, error_response(
                "Admin passwords must be at least 12 characters", 400
            )

    for field, limit in (("full_name", 100), ("status", 20)):
        if field not in data:
            continue
        data[field], error = validate_optional_string_field(data, field, limit)
        if error:
            return None, error
        if field == "status" and data[field] is None:
            return None, error_response("status must be a string", 400)

    return data, None


@users_bp.post("/users")
@admin_required
def create_user():
    data, error = _validate_user_payload(creating=True)
    if error:
        return error
    try:
        user = user_service.create_user(data)
    except ServiceError as error:
        return service_error_response(error)
    except IntegrityError as error:
        return database_error_response(
            "user.create", error, conflict_message="Username already exists"
        )
    except SQLAlchemyError as error:
        return database_error_response("user.create", error)
    except (AttributeError, TypeError, ValueError) as error:
        return unexpected_error_response("user.create", error)

    return success_response(user.to_dict(), 201)


@users_bp.get("/users")
@admin_required
def get_users():
    try:
        users = user_service.list_users()
        return success_response([user.to_dict() for user in users])
    except SQLAlchemyError as error:
        return database_error_response("user.list", error)
    except (AttributeError, TypeError, ValueError) as error:
        return unexpected_error_response("user.list", error)


@users_bp.get("/users/<int:user_id>")
@admin_required
def get_user(user_id):
    try:
        user = user_service.get_user(user_id)
        if user is None:
            return error_response("User not found", 404)
        return success_response(user.to_dict())
    except SQLAlchemyError as error:
        return database_error_response("user.get", error)
    except (AttributeError, TypeError, ValueError) as error:
        return unexpected_error_response("user.get", error)


@users_bp.put("/users/<int:user_id>")
@admin_required
def update_user(user_id):
    try:
        existing_user = user_service.get_user(user_id)
    except SQLAlchemyError as error:
        return database_error_response("user.get", error)
    if existing_user is None:
        return error_response("User not found", 404)

    data, error = _validate_user_payload(creating=False)
    if error:
        return error
    try:
        user = user_service.update_user(existing_user, data)
    except ServiceError as error:
        return service_error_response(error)
    except IntegrityError as error:
        return database_error_response(
            "user.update", error, conflict_message="Username already exists"
        )
    except SQLAlchemyError as error:
        return database_error_response("user.update", error)
    except (AttributeError, TypeError, ValueError) as error:
        return unexpected_error_response("user.update", error)

    return success_response(user.to_dict())


@users_bp.delete("/users/<int:user_id>")
@admin_required
def delete_user(user_id):
    try:
        user_service.delete_user(user_id)
    except ServiceError as error:
        return service_error_response(error)
    except IntegrityError as error:
        return database_error_response(
            "user.delete", error, conflict_message="User cannot be deleted"
        )
    except SQLAlchemyError as error:
        return database_error_response("user.delete", error)

    return success_response({"message": "User deleted"}, 200)
