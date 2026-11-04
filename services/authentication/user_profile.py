from flask import Blueprint, current_app, jsonify
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from api.authentication.validation import (
    validate_integer_field,
    validate_json_request,
    validate_optional_string_field,
    validate_string_field,
)
from database import db
from database.models.profile import UserProfile
from database.models.user import User

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
            return None, (jsonify({"error": f"{field} must not exceed 50 characters"}), 400)

    for field, limit in (("middle_name", 50), ("contact_number", 20)):
        if field in data:
            data[field], error = validate_optional_string_field(data, field, limit)
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


@profiles_bp.post("/user_profiles")
def create_profile():
    data, error = _validate_profile_payload(creating=True)
    if error:
        return error

    try:
        if not db.session.get(User, data["user_id"]):
            return jsonify({"error": "user_id does not exist"}), 400
        if db.session.get(UserProfile, data["user_id"]):
            return jsonify({"error": "Profile already exists for this user"}), 409

        profile = UserProfile(
            user_id=data["user_id"],
            first_name=data["first_name"],
            middle_name=data.get("middle_name"),
            last_name=data["last_name"],
            contact_number=data.get("contact_number"),
        )
        db.session.add(profile)
        db.session.commit()
        return jsonify(profile.to_dict()), 201
    except IntegrityError as error:
        return _database_failure(
            "profile.create", error, conflict_message="Profile already exists for this user"
        )
    except SQLAlchemyError as error:
        return _database_failure("profile.create", error)
    except (AttributeError, TypeError, ValueError) as error:
        return _database_failure("profile.create", error)


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
        profiles = db.session.query(UserProfile).all()
        return jsonify([profile.to_dict() for profile in profiles])
    except SQLAlchemyError as error:
        return _database_failure("profile.list", error)
    except (AttributeError, TypeError, ValueError) as error:
        return _database_failure("profile.list", error)


@profiles_bp.get("/user_profiles/<int:user_id>")
def get_profile(user_id):
    try:
        profile = db.session.get(UserProfile, user_id)
        if not profile:
            return jsonify({"error": "Profile not found"}), 404
        return jsonify(profile.to_dict())
    except SQLAlchemyError as error:
        return _database_failure("profile.get", error)
    except (AttributeError, TypeError, ValueError) as error:
        return _database_failure("profile.get", error)


@profiles_bp.put("/user_profiles/<int:user_id>")
def update_profile(user_id):
    try:
        profile = db.session.get(UserProfile, user_id)
        if not profile:
            return jsonify({"error": "Profile not found"}), 404

        data, error = _validate_profile_payload(creating=False)
        if error:
            return error

        profile.first_name = data["first_name"]
        profile.middle_name = data.get("middle_name")
        profile.last_name = data["last_name"]
        profile.contact_number = data.get("contact_number")
        db.session.commit()
        return jsonify(profile.to_dict())
    except IntegrityError as error:
        return _database_failure("profile.update", error, conflict_message="Profile cannot be updated")
    except SQLAlchemyError as error:
        return _database_failure("profile.update", error)
    except (AttributeError, TypeError, ValueError) as error:
        return _database_failure("profile.update", error)


@profiles_bp.delete("/user_profiles/<int:user_id>")
def delete_profile(user_id):
    try:
        profile = db.session.get(UserProfile, user_id)
        if not profile:
            return jsonify({"error": "Profile not found"}), 404
        db.session.delete(profile)
        db.session.commit()
        return jsonify({"message": "Profile deleted"}), 200
    except IntegrityError as error:
        return _database_failure(
            "profile.delete", error, conflict_message="Profile cannot be deleted"
        )
    except SQLAlchemyError as error:
        return _database_failure("profile.delete", error)
