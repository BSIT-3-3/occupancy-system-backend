from sqlalchemy.exc import SQLAlchemyError
from werkzeug.security import generate_password_hash

from database.extensions import db
from database.models.profile import UserProfile
from database.models.role import Role
from database.models.user import User
from services.errors import (
    ConflictError,
    InvalidReferenceError,
    NotFoundError,
)

ADMIN_ROLE_NAME = "ADMIN"
PUBLIC_REGISTRATION_ROLE = "USER"


def register_user(data):
    """Create a public USER account and its profile atomically."""
    try:
        if username_taken(data["username"]):
            raise ConflictError("Username already exists")

        role = Role.query.filter_by(role_name=PUBLIC_REGISTRATION_ROLE).first()
        if role is None:
            role = Role(
                role_name=PUBLIC_REGISTRATION_ROLE,
                description="Registered user",
            )
            db.session.add(role)
            db.session.flush()

        full_name = " ".join(
            filter(
                None,
                [data["first_name"], data.get("middle_name"), data["last_name"]],
            )
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
        return user
    except SQLAlchemyError:
        db.session.rollback()
        raise


def username_taken(username, exclude_id=None):
    query = db.session.query(User).filter(User.username == username)
    if exclude_id is not None:
        query = query.filter(User.user_id != exclude_id)
    return query.first() is not None


def create_user(data):
    try:
        role = db.session.get(Role, data["role_id"])
        if role is None or role.role_name != ADMIN_ROLE_NAME:
            raise InvalidReferenceError("Only ADMIN accounts are supported")
        if username_taken(data["username"]):
            raise ConflictError("Username already exists")

        user = User(
            username=data["username"],
            password=generate_password_hash(data["password"]),
            full_name=data.get("full_name"),
            role_id=data["role_id"],
            status=data.get("status", "active"),
        )
        db.session.add(user)
        db.session.commit()
        return user
    except SQLAlchemyError:
        db.session.rollback()
        raise


def list_users():
    return db.session.query(User).all()


def get_user(user_id):
    return db.session.get(User, user_id)


def update_user(user, data):
    try:
        role = db.session.get(Role, data["role_id"])
        if role is None or role.role_name != ADMIN_ROLE_NAME:
            raise InvalidReferenceError("Only ADMIN accounts are supported")
        if username_taken(data["username"], exclude_id=user.user_id):
            raise ConflictError("Username already exists")

        user.username = data["username"]
        user.full_name = data.get("full_name")
        user.role_id = data["role_id"]
        user.status = data.get("status", "active")
        if data.get("password"):
            user.password = generate_password_hash(data["password"])
        db.session.commit()
        return user
    except SQLAlchemyError:
        db.session.rollback()
        raise


def delete_user(user_id):
    try:
        user = get_user(user_id)
        if user is None:
            raise NotFoundError("User not found")
        db.session.delete(user)
        db.session.commit()
        return True
    except SQLAlchemyError:
        db.session.rollback()
        raise
