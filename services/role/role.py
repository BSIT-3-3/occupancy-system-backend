from flask import Blueprint, request, jsonify
from sqlalchemy.exc import IntegrityError

from database import db
from database.models.role import Role

roles_bp = Blueprint("roles", __name__)


# CREATE
@roles_bp.post("/roles")
def create_role():
    data = request.get_json()

    role = Role(
        role_name=data["role_name"],
        description=data.get("description")
    )

    db.session.add(role)
    db.session.commit()

    return jsonify(role.to_dict()), 201


# READ ALL
@roles_bp.get("/roles")
def get_roles():
    roles = db.session.query(Role).all()
    return jsonify([role.to_dict() for role in roles])


# READ ONE
@roles_bp.get("/roles/<int:role_id>")
def get_role(role_id):
    role = db.session.get(Role, role_id)

    if not role:
        return jsonify({"error": "Role not found"}), 404

    return jsonify(role.to_dict())


# UPDATE
@roles_bp.put("/roles/<int:role_id>")
def update_role(role_id):
    data = request.get_json()
    role = db.session.get(Role, role_id)

    if not role:
        return jsonify({"error": "Role not found"}), 404

    role.role_name = data["role_name"]
    role.description = data.get("description")

    db.session.commit()

    return jsonify(role.to_dict())


# DELETE
@roles_bp.delete("/roles/<int:role_id>")
def delete_role(role_id):
    role = db.session.get(Role, role_id)

    if not role:
        return jsonify({"error": "Role not found"}), 404

    try:
        db.session.delete(role)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({"error": "Role is assigned to users"}), 409

    return jsonify({"message": "Role deleted"}), 200
