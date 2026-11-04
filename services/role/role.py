from sqlalchemy.exc import SQLAlchemyError

from database.extensions import db
from database.models.role import Role
from services.errors import ConflictError, InvalidReferenceError, NotFoundError

ADMIN_ROLE_NAME = "ADMIN"


def create_role(data):
    try:
        if data["role_name"].upper() != ADMIN_ROLE_NAME:
            raise InvalidReferenceError("Only the ADMIN role is supported")
        role = Role(role_name=data["role_name"], description=data.get("description"))
        db.session.add(role)
        db.session.commit()
        return role
    except SQLAlchemyError:
        db.session.rollback()
        raise


def list_roles():
    return db.session.query(Role).filter_by(role_name=ADMIN_ROLE_NAME).all()


def get_role(role_id):
    role = db.session.get(Role, role_id)
    return role if role and role.role_name == ADMIN_ROLE_NAME else None


def update_role(role, data):
    try:
        if data["role_name"].upper() != ADMIN_ROLE_NAME:
            raise InvalidReferenceError("Only the ADMIN role is supported")
        role.role_name = data["role_name"]
        role.description = data.get("description")
        db.session.commit()
        return role
    except SQLAlchemyError:
        db.session.rollback()
        raise


def delete_role(role_id):
    role = get_role(role_id)
    if role is None:
        raise NotFoundError("Role not found")
    raise ConflictError("The ADMIN role cannot be deleted")
