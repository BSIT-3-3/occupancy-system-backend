from database.extensions import db


class EmergencyBroadcast(db.Model):
    __tablename__ = "emergency_broadcast"

    broadcast_id = db.Column(db.Integer, primary_key=True)
    message_text = db.Column(db.String(500), nullable=False)
    created_by = db.Column(db.Integer, nullable=False)
    created_at = db.Column(
        db.DateTime(timezone=True), server_default=db.func.now(), nullable=False
    )

    targets = db.relationship(
        "EmergencyBroadcastTarget",
        back_populates="broadcast",
        cascade="all, delete-orphan",
    )


class EmergencyBroadcastTarget(db.Model):
    __tablename__ = "emergency_broadcast_target"

    target_id = db.Column(db.Integer, primary_key=True)
    broadcast_id = db.Column(
        db.Integer,
        db.ForeignKey("emergency_broadcast.broadcast_id"),
        nullable=False,
        index=True,
    )
    room_id = db.Column(
        db.Integer, db.ForeignKey("room.room_id"), nullable=False, index=True
    )
    delivery_status = db.Column(
        db.String(20), nullable=False, default="PENDING", server_default="PENDING"
    )
    dispatched_at = db.Column(db.DateTime(timezone=True))
    acknowledged_at = db.Column(db.DateTime(timezone=True))
    failure_reason = db.Column(db.String(250))

    broadcast = db.relationship("EmergencyBroadcast", back_populates="targets")
    room = db.relationship("Room")

    __table_args__ = (
        db.UniqueConstraint("broadcast_id", "room_id", name="uq_broadcast_target_room"),
        db.CheckConstraint(
            "delivery_status IN ('PENDING', 'DISPATCHED', 'ACKNOWLEDGED', 'FAILED')",
            name="ck_broadcast_target_status",
        ),
    )
