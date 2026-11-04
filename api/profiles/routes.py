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
from services.authentication import user_profile as profile_service
from services.errors import ServiceError

profiles_bp = Blueprint("user_profiles", __name__)


def _validate_profile_payload(*, creating):
    required = ["first_name", "last_name"]
    if creating:
        required.insert(0, "user_id")
    data, error = validate_json_request(required)
    if error:
        return None, error

    if creating:
        data["user_id"], error = validate_integer_field(data, "user_id")
        if error:
            return None, error

    for field in ("first_name", "last_name"):
        data[field], error = validate_string_field(data, field)
        if error:
            return None, error
        if len(data[field]) > 50:
            return None, error_response(f"{field} must not exceed 50 characters", 400)

    for field, limit in (("middle_name", 50), ("contact_number", 20)):
        if field in data:
            data[field], error = validate_optional_string_field(data, field, limit)
            if error:
                return None, error
    return data, None


@profiles_bp.post("/user_profiles")
def create_profile():
    data, error = _validate_profile_payload(creating=True)
    if error:
        return error
    try:
        profile = profile_service.create_profile(data)
    except ServiceError as error:
        return service_error_response(error)
    except IntegrityError as error:
        return database_error_response(
            "profile.create",
            error,
            conflict_message="Profile already exists for this user",
        )
    except SQLAlchemyError as error:
        return database_error_response("profile.create", error)
    except (AttributeError, TypeError, ValueError) as error:
        return unexpected_error_response("profile.create", error)

    return success_response(profile.to_dict(), 201)


@profiles_bp.get("/user_profiles")
def get_profiles():
    """
    Get all user profiles.
    ---
    tags:
      - User Profiles
    responses:
      200:
        description: List of user profiles
    """
    try:
        profiles = profile_service.list_profiles()
        return success_response([profile.to_dict() for profile in profiles])
    except SQLAlchemyError as error:
        return database_error_response("profile.list", error)
    except (AttributeError, TypeError, ValueError) as error:
        return unexpected_error_response("profile.list", error)


@profiles_bp.get("/user_profiles/<int:user_id>")
def get_profile(user_id):
    try:
        profile = profile_service.get_profile(user_id)
        if profile is None:
            return error_response("Profile not found", 404)
        return success_response(profile.to_dict())
    except SQLAlchemyError as error:
        return database_error_response("profile.get", error)
    except (AttributeError, TypeError, ValueError) as error:
        return unexpected_error_response("profile.get", error)


@profiles_bp.put("/user_profiles/<int:user_id>")
def update_profile(user_id):
    try:
        existing_profile = profile_service.get_profile(user_id)
    except SQLAlchemyError as error:
        return database_error_response("profile.get", error)
    if existing_profile is None:
        return error_response("Profile not found", 404)

    data, error = _validate_profile_payload(creating=False)
    if error:
        return error
    try:
        profile = profile_service.update_profile(existing_profile, data)
    except ServiceError as error:
        return service_error_response(error)
    except IntegrityError as error:
        return database_error_response(
            "profile.update", error, conflict_message="Profile cannot be updated"
        )
    except SQLAlchemyError as error:
        return database_error_response("profile.update", error)
    except (AttributeError, TypeError, ValueError) as error:
        return unexpected_error_response("profile.update", error)

    return success_response(profile.to_dict())


@profiles_bp.delete("/user_profiles/<int:user_id>")
def delete_profile(user_id):
    try:
        profile_service.delete_profile(user_id)
    except ServiceError as error:
        return service_error_response(error)
    except IntegrityError as error:
        return database_error_response(
            "profile.delete", error, conflict_message="Profile cannot be deleted"
        )
    except SQLAlchemyError as error:
        return database_error_response("profile.delete", error)

    return success_response({"message": "Profile deleted"}, 200)
