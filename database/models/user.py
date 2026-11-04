from database.extensions import db


class User(db.Model):
    __tablename__ = "users"

    user_id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    full_name = db.Column(db.String(100))
    role_id = db.Column(db.Integer, db.ForeignKey("role.role_id"), nullable=False)
    status = db.Column(db.String(20), nullable=False, default="ACTIVE")
    created_at = db.Column(
        db.DateTime(timezone=True), server_default=db.func.now(), nullable=False
    )

    role = db.relationship("Role", backref="users")

    def to_dict(self):
        """Return public user fields without exposing the password hash."""
        return {
            "user_id": self.user_id,
            "username": self.username,
            "full_name": self.full_name,
            "role_id": self.role_id,
            "status": self.status,
        }
