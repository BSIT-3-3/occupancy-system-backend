from flask import Flask, request, jsonify
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, func

from db import Base, Session, engine
from user import User  # needed so the user table exists for the foreign key

app = Flask(__name__)


class UserProfile(Base):
    __tablename__ = "user_profile"

    # one profile per user: user_id is both primary key and foreign key
    user_id = Column(
        Integer, ForeignKey("user.user_id", ondelete="CASCADE"), primary_key=True
    )
    first_name = Column(String(50), nullable=False)
    middle_name = Column(String(50))
    last_name = Column(String(50), nullable=False)
    contact_number = Column(String(20))
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    def to_dict(self):
        return {
            "user_id": self.user_id,
            "first_name": self.first_name,
            "middle_name": self.middle_name,
            "last_name": self.last_name,
            "contact_number": self.contact_number,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


# CREATE
@app.post("/user_profiles")
def create_profile():
    data = request.get_json()
    with Session() as s:
        if not s.get(User, data["user_id"]):
            return jsonify({"error": "user_id does not exist"}), 400
        if s.get(UserProfile, data["user_id"]):
            return jsonify({"error": "Profile already exists for this user"}), 409
        profile = UserProfile(
            user_id=data["user_id"],
            first_name=data["first_name"],
            middle_name=data.get("middle_name"),
            last_name=data["last_name"],
            contact_number=data.get("contact_number"),
        )
        s.add(profile)
        s.commit()
        return jsonify(profile.to_dict()), 201


# READ ALL
@app.get("/user_profiles")
def get_profiles():
    with Session() as s:
        return jsonify([p.to_dict() for p in s.query(UserProfile).all()])


# READ ONE
@app.get("/user_profiles/<int:user_id>")
def get_profile(user_id):
    with Session() as s:
        profile = s.get(UserProfile, user_id)
        if not profile:
            return jsonify({"error": "Profile not found"}), 404
        return jsonify(profile.to_dict())


# UPDATE
@app.put("/user_profiles/<int:user_id>")
def update_profile(user_id):
    data = request.get_json()
    with Session() as s:
        profile = s.get(UserProfile, user_id)
        if not profile:
            return jsonify({"error": "Profile not found"}), 404
        profile.first_name = data["first_name"]
        profile.middle_name = data.get("middle_name")
        profile.last_name = data["last_name"]
        profile.contact_number = data.get("contact_number")
        s.commit()
        return jsonify(profile.to_dict())


# DELETE
@app.delete("/user_profiles/<int:user_id>")
def delete_profile(user_id):
    with Session() as s:
        profile = s.get(UserProfile, user_id)
        if not profile:
            return jsonify({"error": "Profile not found"}), 404
        s.delete(profile)
        s.commit()
        return jsonify({"message": "Profile deleted"})


if __name__ == "__main__":
    Base.metadata.create_all(engine)
    app.run(port=5003, debug=True)
