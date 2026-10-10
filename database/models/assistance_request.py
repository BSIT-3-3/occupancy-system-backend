
from database.extensions import db


class AssistanceRequest(db.Model):
    __tablename__ = "assistance_request"

    assistance_request_id = db.Column(
        db.Integer, primary_key=True, 
    )
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
    status = db.Column(
        db.String(30), nullable=False, default="PENDING"
    )
    requested_at = db.Column(
        db.DateTime(timezone=True),
        server_default=db.func.now(),
        nullable=False
    )
    acknowledged_at = db.Column(db.DateTime(timezone=True))
    resolved_at = db.Column(db.DateTime(timezone=True))
    remarks = db.Column(db.Text)
