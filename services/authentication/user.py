from flask import Blueprint, request, jsonify
from sqlalchemy.exc import IntegrityError
from werkzeug.security import generate_password_hash

from database import db
from database.models.user import User
from database.models.role import Role

users_bp = Blueprint("users", __name__)


def username_taken(username, exclude_id=None):
    query = db.session.query(User).filter(
        User.username == username
    )

    if exclude_id is not None:
        query = query.filter(User.user_id != exclude_id)

    return query.first() is not None


# CREATE
@users_bp.post("/users")
def create_user():
    data = request.get_json()

    if not db.session.get(Role, data["role_id"]):
        return jsonify({"error": "role_id does not exist"}), 400

    if username_taken(data["username"]):
        return jsonify({"error": "Username already exists"}), 409

    user = User(
        username=data["username"],
        password=generate_password_hash(data["password"]),
        full_name=data.get("full_name"),
        role_id=data["role_id"],
        status=data.get("status", "active"),
    )

    db.session.add(user)
    db.session.commit()

    return jsonify(user.to_dict()), 201


# READ ALL
@users_bp.get("/users")
def get_users():
    users = db.session.query(User).all()
    return jsonify([user.to_dict() for user in users])


# READ ONE
@users_bp.get("/users/<int:user_id>")
def get_user(user_id):
    user = db.session.get(User, user_id)

    if not user:
        return jsonify({"error": "User not found"}), 404

    return jsonify(user.to_dict())


# UPDATE
@users_bp.put("/users/<int:user_id>")
def update_user(user_id):
    data = request.get_json()
    user = db.session.get(User, user_id)

    if not user:
        return jsonify({"error": "User not found"}), 404

    if not db.session.get(Role, data["role_id"]):
        return jsonify({"error": "role_id does not exist"}), 400

    if username_taken(data["username"], exclude_id=user_id):
        return jsonify({"error": "Username already exists"}), 409

    user.username = data["username"]
    user.full_name = data.get("full_name")
    user.role_id = data["role_id"]
    user.status = data.get("status", "active")

    if data.get("password"):
        user.password = generate_password_hash(data["password"])

    db.session.commit()

    return jsonify(user.to_dict())


# DELETE
@users_bp.delete("/users/<int:user_id>")
def delete_user(user_id):
    user = db.session.get(User, user_id)

    if not user:
        return jsonify({"error": "User not found"}), 404

    try:
        db.session.delete(user)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({"error": "User cannot be deleted"}), 409

    return jsonify({"message": "User deleted"}), 200