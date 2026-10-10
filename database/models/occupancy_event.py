
from database.extensions import db


class OccupancyEvent(db.Model):
    __tablename__ = "occupancy_event"

    occupancy_event_id = db.Column(db.Integer, primary_key=True)
    room_id = db.Column(
        db.Integer,
        db.ForeignKey("room.room_id"),
        nullable=False
    )
    device_id = db.Column(
        db.String(20),
        db.ForeignKey("room_device.device_id"),
        nullable=False
    )
    event_type = db.Column(db.String(30), nullable=False)
    occupancy_status = db.Column(db.String(20), nullable=False)
    occurred_at = db.Column(
        db.DateTime(timezone=True),
        server_default=db.func.now(),
        nullable=False
    )
