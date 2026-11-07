from database.extensions import db


class UserSession(db.Model):
    __tablename__ = "user_sessions"

    session_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_at = db.Column(
        db.DateTime(timezone=True), server_default=db.func.now(), nullable=False
    )
    last_seen_at = db.Column(db.DateTime(timezone=True))
    expires_at = db.Column(db.DateTime(timezone=True), nullable=False)
    revoked_at = db.Column(db.DateTime(timezone=True))
    revoke_reason = db.Column(db.String(32))

    user = db.relationship(
        "User",
        backref=db.backref(
            "sessions", cascade="all, delete-orphan", passive_deletes=True
        ),
    )
    refresh_tokens = db.relationship(
        "RefreshToken",
        back_populates="session",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
