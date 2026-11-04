from sqlalchemy.exc import SQLAlchemyError

from database.extensions import db
from database.models.role import Role
from services.errors import NotFoundError


def create_role(data):
    try:
        role = Role(role_name=data["role_name"], description=data.get("description"))
        db.session.add(role)
        db.session.commit()
        return role
    except SQLAlchemyError:
        db.session.rollback()
        raise


def list_roles():
    return db.session.query(Role).all()


def get_role(role_id):
    return db.session.get(Role, role_id)


def update_role(role, data):
    try:
        role.role_name = data["role_name"]
        role.description = data.get("description")
        db.session.commit()
        return role
    except SQLAlchemyError:
        db.session.rollback()
        raise


def delete_role(role_id):
    try:
        role = get_role(role_id)
        if role is None:
            raise NotFoundError("Role not found")
        db.session.delete(role)
        db.session.commit()
        return True
    except SQLAlchemyError:
        db.session.rollback()
        raise
