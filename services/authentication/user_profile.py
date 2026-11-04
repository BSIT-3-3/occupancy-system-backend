from sqlalchemy.exc import SQLAlchemyError

from database.extensions import db
from database.models.profile import UserProfile
from database.models.user import User
from services.errors import ConflictError, InvalidReferenceError, NotFoundError


def create_profile(data):
    try:
        if db.session.get(User, data["user_id"]) is None:
            raise InvalidReferenceError("user_id does not exist")
        if db.session.get(UserProfile, data["user_id"]) is not None:
            raise ConflictError("Profile already exists for this user")

        profile = UserProfile(
            user_id=data["user_id"],
            first_name=data["first_name"],
            middle_name=data.get("middle_name"),
            last_name=data["last_name"],
            contact_number=data.get("contact_number"),
        )
        db.session.add(profile)
        db.session.commit()
        return profile
    except SQLAlchemyError:
        db.session.rollback()
        raise


def list_profiles():
    return db.session.query(UserProfile).all()


def get_profile(user_id):
    return db.session.get(UserProfile, user_id)


def update_profile(profile, data):
    try:
        profile.first_name = data["first_name"]
        profile.middle_name = data.get("middle_name")
        profile.last_name = data["last_name"]
        profile.contact_number = data.get("contact_number")
        db.session.commit()
        return profile
    except SQLAlchemyError:
        db.session.rollback()
        raise


def delete_profile(user_id):
    try:
        profile = get_profile(user_id)
        if profile is None:
            raise NotFoundError("Profile not found")
        db.session.delete(profile)
        db.session.commit()
        return True
    except SQLAlchemyError:
        db.session.rollback()
        raise
