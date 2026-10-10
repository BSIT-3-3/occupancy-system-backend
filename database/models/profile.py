
from database.extensions import db


class UserProfile(db.Model):
    __tablename__ = "user_profile"

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.user_id"),
        primary_key=True
    )
    first_name = db.Column(db.String(50), nullable=False)
    middle_name = db.Column(db.String(50))
    last_name = db.Column(db.String(50), nullable=False)
    contact_number = db.Column(db.String(20))
    updated_at = db.Column(
        db.DateTime(timezone=True),
        onupdate=db.func.now()
    )

    user = db.relationship(
        "User",
        backref=db.backref("profile", uselist=False)
    )
