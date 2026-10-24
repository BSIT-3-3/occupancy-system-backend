from flask import Blueprint, request, jsonify
from sqlalchemy.exc import IntegrityError

from database import db
from database.models.user import User
from database.models.profile import UserProfile

profiles_bp = Blueprint("user_profiles", __name__)


# CREATE
@profiles_bp.post("/user_profiles")
def create_profile():
    data = request.get_json()

    if not db.session.get(User, data["user_id"]):
        return jsonify({"error": "user_id does not exist"}), 400

    if db.session.get(UserProfile, data["user_id"]):
        return jsonify({
            "error": "Profile already exists for this user"
        }), 409

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


# READ ALL
# READ ALL
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
    profiles = db.session.query(UserProfile).all()
    return jsonify([profile.to_dict() for profile in profiles])

# READ ONE
@profiles_bp.get("/user_profiles/<int:user_id>")
def get_profile(user_id):
    profile = db.session.get(UserProfile, user_id)

    if not profile:
        return jsonify({"error": "Profile not found"}), 404

    return jsonify(profile.to_dict())


# UPDATE
@profiles_bp.put("/user_profiles/<int:user_id>")
def update_profile(user_id):
    data = request.get_json()
    profile = db.session.get(UserProfile, user_id)

    if not profile:
        return jsonify({"error": "Profile not found"}), 404

    profile.first_name = data["first_name"]
    profile.middle_name = data.get("middle_name")
    profile.last_name = data["last_name"]
    profile.contact_number = data.get("contact_number")

    db.session.commit()

    return jsonify(profile.to_dict())


# DELETE
@profiles_bp.delete("/user_profiles/<int:user_id>")
def delete_profile(user_id):
    profile = db.session.get(UserProfile, user_id)

    if not profile:
        return jsonify({"error": "Profile not found"}), 404

    try:
        db.session.delete(profile)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({"error": "Profile cannot be deleted"}), 409

    return jsonify({"message": "Profile deleted"}), 200
