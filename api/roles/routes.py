from flask import Blueprint
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from api.authentication.validation import (
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
from database.extensions import limiter
from services.errors import ServiceError
from services.role import role as role_service
from services.security.rate_limits import READ, WRITE

roles_bp = Blueprint("roles", __name__)


def _validate_role_payload():
    data, error = validate_json_request(["role_name"])
    if error:
        return None, error

    data["role_name"], error = validate_string_field(data, "role_name")
    if error:
        return None, error
    if len(data["role_name"]) > 50:
        return None, error_response("role_name must not exceed 50 characters", 400)
    data["role_name"] = data["role_name"].upper()

    if "description" in data:
        data["description"], error = validate_optional_string_field(
            data, "description", 25
        )
        if error:
            return None, error
    return data, None


@roles_bp.post("/roles")
@limiter.limit(WRITE)
@admin_required
def create_role():
    data, error = _validate_role_payload()
    if error:
        return error
    try:
        role = role_service.create_role(data)
    except ServiceError as error:
        return service_error_response(error)
    except IntegrityError as error:
        return database_error_response(
            "role.create", error, conflict_message="Role already exists"
        )
    except SQLAlchemyError as error:
        return database_error_response("role.create", error)
    except (AttributeError, TypeError, ValueError) as error:
        return unexpected_error_response("role.create", error)
    return success_response(role.to_dict(), 201)


@roles_bp.get("/roles")
@limiter.limit(READ)
@admin_required
def get_roles():
    try:
        roles = role_service.list_roles()
        return success_response([role.to_dict() for role in roles])
    except SQLAlchemyError as error:
        return database_error_response("role.list", error)
    except (AttributeError, TypeError, ValueError) as error:
        return unexpected_error_response("role.list", error)


@roles_bp.get("/roles/<int:role_id>")
@limiter.limit(READ)
@admin_required
def get_role(role_id):
    try:
        role = role_service.get_role(role_id)
        if role is None:
            return error_response("Role not found", 404)
        return success_response(role.to_dict())
    except SQLAlchemyError as error:
        return database_error_response("role.get", error)
    except (AttributeError, TypeError, ValueError) as error:
        return unexpected_error_response("role.get", error)


@roles_bp.put("/roles/<int:role_id>")
@limiter.limit(WRITE)
@admin_required
def update_role(role_id):
    try:
        existing_role = role_service.get_role(role_id)
    except SQLAlchemyError as error:
        return database_error_response("role.get", error)
    if existing_role is None:
        return error_response("Role not found", 404)

    data, error = _validate_role_payload()
    if error:
        return error
    try:
        role = role_service.update_role(existing_role, data)
    except ServiceError as error:
        return service_error_response(error)
    except IntegrityError as error:
        return database_error_response(
            "role.update", error, conflict_message="Role already exists"
        )
    except SQLAlchemyError as error:
        return database_error_response("role.update", error)
    except (AttributeError, TypeError, ValueError) as error:
        return unexpected_error_response("role.update", error)

    return success_response(role.to_dict())


@roles_bp.delete("/roles/<int:role_id>")
@limiter.limit(WRITE)
@admin_required
def delete_role(role_id):
    try:
        role_service.delete_role(role_id)
    except ServiceError as error:
        return service_error_response(error)
    except IntegrityError as error:
        return database_error_response(
            "role.delete", error, conflict_message="Role is assigned to users"
        )
    except SQLAlchemyError as error:
        return database_error_response("role.delete", error)

    return success_response({"message": "Role deleted"}, 200)
