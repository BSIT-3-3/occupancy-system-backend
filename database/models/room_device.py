from database.extensions import db


class RoomDevice(db.Model):
    __tablename__ = "room_device"

    device_id = db.Column(db.String(20), primary_key=True)
    room_id = db.Column(
        db.Integer, db.ForeignKey("room.room_id"), nullable=False, unique=True
    )
    device_code = db.Column(db.String(50), unique=True, nullable=False)
    device_name = db.Column(db.String(50))
    registration_status = db.Column(db.String(30))
    credential_hash = db.Column(db.String(64), nullable=True)
    registered_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now())
    current_status = db.Column(
        db.String(10), nullable=False, default="UNKNOWN", server_default="UNKNOWN"
    )
    last_communication_at = db.Column(db.DateTime(timezone=True))

    __table_args__ = (
        db.UniqueConstraint(
            "credential_hash", name="uq_room_device_credential_hash"
        ),
        db.CheckConstraint(
            "current_status IN ('UNKNOWN', 'ONLINE', 'OFFLINE')",
            name="ck_room_device_current_status",
        ),

    )

    room = db.relationship("Room", backref="device", uselist=False)
    status_history = db.relationship(
        "DeviceStatusLog",
        back_populates="device",
        order_by="DeviceStatusLog.changed_at.desc()",
        passive_deletes="all",
    )

    def to_dict(self):
        return {
            "device_id": self.device_id,
            "room_id": self.room_id,
            "device_code": self.device_code,
            "device_name": self.device_name,
            "registration_status": self.registration_status,
            "registered_at": (
                self.registered_at.isoformat() if self.registered_at else None
            ),
            "room": (
                {
                    "room_id": self.room.room_id,
                    "room_number": self.room.room_number,
                    "room_name": self.room.room_name,
                    "is_active": self.room.is_active,
                }
                if self.room is not None
                else None
            ),
        }
