
from database.extensions import db


class RoomDevice(db.Model):
    __tablename__ = "room_device"

    device_id = db.Column(db.String(20), primary_key=True)
    room_id = db.Column(
        db.Integer,
        db.ForeignKey("room.room_id"),
        nullable=False,
        unique=True
    )
    device_code = db.Column(
        db.String(50), unique=True, nullable=False
    )
    device_name = db.Column(db.String(50))
    registration_status = db.Column(db.String(30))
    registered_at = db.Column(
        db.DateTime(timezone=True),
        server_default=db.func.now()
    )

    room = db.relationship("Room", backref="device", uselist=False)
