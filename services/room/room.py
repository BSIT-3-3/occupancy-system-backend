from sqlalchemy.exc import SQLAlchemyError

from database.extensions import db
from database.models.room import Room
from services.errors import ConflictError


def list_rooms():
    return db.session.query(Room).order_by(Room.room_number, Room.room_id).all()


def get_room(room_id):
    return db.session.get(Room, room_id)


def create_room(data):
    try:
        if db.session.query(Room).filter_by(room_number=data["room_number"]).first():
            raise ConflictError("Room number already exists")

        room = Room(
            room_number=data["room_number"],
            room_name=data["room_name"],
            is_active=data.get("is_active", True),
        )
        db.session.add(room)
        db.session.commit()
        return room
    except SQLAlchemyError:
        db.session.rollback()
        raise


def update_room(room, data):
    try:
        if "room_number" in data:
            duplicate = (
                db.session.query(Room.room_id)
                .filter(
                    Room.room_number == data["room_number"],
                    Room.room_id != room.room_id,
                )
                .first()
            )
            if duplicate:
                raise ConflictError("Room number already exists")
            room.room_number = data["room_number"]

        if "room_name" in data:
            room.room_name = data["room_name"]
        if "is_active" in data:
            room.is_active = data["is_active"]

        db.session.commit()
        return room
    except SQLAlchemyError:
        db.session.rollback()
        raise


def deactivate_room(room):
    try:
        room.is_active = False
        db.session.commit()
        return room
    except SQLAlchemyError:
        db.session.rollback()
        raise
