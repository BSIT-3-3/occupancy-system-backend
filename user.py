from flask import Flask, request, jsonify
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, func
from werkzeug.security import generate_password_hash

from db import Base, Session, engine
from role import Role  # needed so the role table exists for the foreign key

app = Flask(__name__)


class User(Base):
    __tablename__ = "user"

    user_id = Column(Integer, primary_key=True)
    username = Column(String(50), unique=True, nullable=False)
    password = Column(String(255), nullable=False)
    full_name = Column(String(100))
    role_id = Column(Integer, ForeignKey("role.role_id"), nullable=False)
    status = Column(String(20), default="active")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    def to_dict(self):  # password is never returned
        return {
            "user_id": self.user_id,
            "username": self.username,
            "full_name": self.full_name,
            "role_id": self.role_id,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


def username_taken(s, username, exclude_id=None):
    user = s.query(User).filter(User.username == username).first()
    return user is not None and user.user_id != exclude_id


# CREATE
@app.post("/users")
def create_user():
    data = request.get_json()
    with Session() as s:
        if not s.get(Role, data["role_id"]):
            return jsonify({"error": "role_id does not exist"}), 400
        if username_taken(s, data["username"]):
            return jsonify({"error": "Username already exists"}), 409
        user = User(
            username=data["username"],
            password=generate_password_hash(data["password"]),
            full_name=data.get("full_name"),
            role_id=data["role_id"],
            status=data.get("status", "active"),
        )
        s.add(user)
        s.commit()
        return jsonify(user.to_dict()), 201


# READ ALL
@app.get("/users")
def get_users():
    with Session() as s:
        return jsonify([u.to_dict() for u in s.query(User).all()])


# READ ONE
@app.get("/users/<int:user_id>")
def get_user(user_id):
    with Session() as s:
        user = s.get(User, user_id)
        if not user:
            return jsonify({"error": "User not found"}), 404
        return jsonify(user.to_dict())


# UPDATE (password is only changed if sent)
@app.put("/users/<int:user_id>")
def update_user(user_id):
    data = request.get_json()
    with Session() as s:
        user = s.get(User, user_id)
        if not user:
            return jsonify({"error": "User not found"}), 404
        if not s.get(Role, data["role_id"]):
            return jsonify({"error": "role_id does not exist"}), 400
        if username_taken(s, data["username"], exclude_id=user_id):
            return jsonify({"error": "Username already exists"}), 409
        user.username = data["username"]
        user.full_name = data.get("full_name")
        user.role_id = data["role_id"]
        user.status = data.get("status", "active")
        if "password" in data:
            user.password = generate_password_hash(data["password"])
        s.commit()
        return jsonify(user.to_dict())


# DELETE
@app.delete("/users/<int:user_id>")
def delete_user(user_id):
    with Session() as s:
        user = s.get(User, user_id)
        if not user:
            return jsonify({"error": "User not found"}), 404
        s.delete(user)
        s.commit()
        return jsonify({"message": "User deleted"})


if __name__ == "__main__":
    Base.metadata.create_all(engine)
    app.run(port=5002, debug=True)
