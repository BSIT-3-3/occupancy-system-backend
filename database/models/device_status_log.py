from database.extensions import db


class DeviceStatusLog(db.Model):
    __tablename__ = "device_status_log"

    device_status_id = db.Column(db.Integer, primary_key=True)
    device_id = db.Column(
        db.String(20),
        db.ForeignKey("room_device.device_id"),
        nullable=False,
    )
    previous_status = db.Column(db.String(10), nullable=False)
    new_status = db.Column(db.String(10), nullable=False)
    changed_at = db.Column(
        db.DateTime(timezone=True), server_default=db.func.now(), nullable=False
    )
    reason = db.Column(db.String(50), nullable=False)

    __table_args__ = (
        db.CheckConstraint(
            "previous_status IN ('UNKNOWN', 'ONLINE', 'OFFLINE')",
            name="ck_device_status_log_previous_status",
        ),
        db.CheckConstraint(
            "new_status IN ('UNKNOWN', 'ONLINE', 'OFFLINE')",
            name="ck_device_status_log_new_status",
        ),
        db.CheckConstraint(
            "previous_status <> new_status",
            name="ck_device_status_log_status_changed",
        ),
        db.Index("ix_device_status_log_device_changed_at", "device_id", "changed_at"),
    )

    device = db.relationship("RoomDevice", back_populates="status_history")
