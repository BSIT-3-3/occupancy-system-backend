from database.extensions import db


class RefreshToken(db.Model):
    __tablename__ = "refresh_tokens"

    refresh_token_id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(
        db.Integer,
        db.ForeignKey("user_sessions.session_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    jti = db.Column(db.String(36), nullable=False, unique=True)
    issued_at = db.Column(
        db.DateTime(timezone=True), server_default=db.func.now(), nullable=False
    )
    expires_at = db.Column(db.DateTime(timezone=True), nullable=False, index=True)
    consumed_at = db.Column(db.DateTime(timezone=True))
    revoked_at = db.Column(db.DateTime(timezone=True))
    replaced_by_token_id = db.Column(
        db.Integer,
        db.ForeignKey("refresh_tokens.refresh_token_id", ondelete="SET NULL"),
    )

    session = db.relationship("UserSession", back_populates="refresh_tokens")
    replaced_by = db.relationship(
        "RefreshToken",
        remote_side=[refresh_token_id],
        foreign_keys=[replaced_by_token_id],
        uselist=False,
    )

    __table_args__ = (
        db.Index(
            "uq_refresh_tokens_one_active_per_session",
            "session_id",
            unique=True,
            sqlite_where=db.and_(
                consumed_at.is_(None), revoked_at.is_(None)
            ),
            postgresql_where=db.and_(
                consumed_at.is_(None), revoked_at.is_(None)
            ),
        ),
    )
