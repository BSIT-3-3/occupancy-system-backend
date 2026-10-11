from flask import Flask, request, jsonify
from sqlalchemy import Column, Integer, String
from sqlalchemy.exc import IntegrityError

from db import Base, Session, engine

app = Flask(__name__)

# CREATE
@app.post("/roles")
def create_role():
    data = request.get_json()
    with Session() as s:
        role = Role(role_name=data["role_name"], description=data.get("description"))
        s.add(role)
        s.commit()
        return jsonify(role.to_dict()), 201


# READ ALL
@app.get("/roles")
def get_roles():
    with Session() as s:
        return jsonify([r.to_dict() for r in s.query(Role).all()])


# READ ONE
@app.get("/roles/<int:role_id>")
def get_role(role_id):
    with Session() as s:
        role = s.get(Role, role_id)
        if not role:
            return jsonify({"error": "Role not found"}), 404
        return jsonify(role.to_dict())


# UPDATE
@app.put("/roles/<int:role_id>")
def update_role(role_id):
    data = request.get_json()
    with Session() as s:
        role = s.get(Role, role_id)
        if not role:
            return jsonify({"error": "Role not found"}), 404
        role.role_name = data["role_name"]
        role.description = data.get("description")
        s.commit()
        return jsonify(role.to_dict())


# DELETE
@app.delete("/roles/<int:role_id>")
def delete_role(role_id):
    with Session() as s:
        role = s.get(Role, role_id)
        if not role:
            return jsonify({"error": "Role not found"}), 404
        try:
            s.delete(role)
            s.commit()
        except IntegrityError:
            s.rollback()
            return jsonify({"error": "Role is assigned to users"}), 409
        return jsonify({"message": "Role deleted"})


if __name__ == "__main__":
    Base.metadata.create_all(engine)
    app.run(port=5001, debug=True)
