from database.extensions import db


class Room(db.Model):
    __tablename__ = "room"

    room_id = db.Column(db.Integer, primary_key=True)
    room_number = db.Column(db.String(50), unique=True, nullable=False)
    room_name = db.Column(db.String(50), nullable=False)
    occupancy_status = db.Column(db.String(20), nullable=False, default="AVAILABLE")
    last_occupancy_update = db.Column(db.DateTime(timezone=True))
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    def to_dict(self):
        return {
            "room_id": self.room_id,
            "room_number": self.room_number,
            "room_name": self.room_name,
            "occupancy_status": self.occupancy_status,
            "last_occupancy_update": (
                self.last_occupancy_update.isoformat()
                if self.last_occupancy_update
                else None
            ),
            "is_active": self.is_active,
        }
