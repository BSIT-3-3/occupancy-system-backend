from database.extensions import db
from models import role, room, room_device

def seed_data():
    # Seed Roles
    roles = [
        role(
            role_name="ADMIN",
            description="System administrator"
        ),
        role(
            role_name="STAFF",
            description="Staff member"
        ),
        role(
            role_name="USER",
            description="Regular user"
        ),
    ]

    for role in roles:
        existing = role.query.filter_by(
            role_name=role.role_name
        ).first()

        if not existing:
            db.session.add(role)

    # Seed Rooms
    rooms = [
        Room(
            room_number="101",
            room_name="Computer Laboratory",
            occupancy_status="AVAILABLE",
            is_active=True
        ),
        Room(
            room_number="102",
            room_name="Lecture Room",
            occupancy_status="OCCUPIED",
            is_active=True
        ),
        Room(
            room_number="103",
            room_name="Faculty Room",
            occupancy_status="AVAILABLE",
            is_active=True
        ),
        Room(
            room_number="104",
            room_name="Guidance Office",
            occupancy_status="AVAILABLE",
            is_active=True
        ),
        Room(
            room_number="105",
            room_name="Library",
            occupancy_status="AVAILABLE",
            is_active=True
        ),
        Room(
            room_number="106",
            room_name="Gym",
            occupancy_status="AVAILABLE",
            is_active=True
        ),
        Room(
            room_number="107",
            room_name="Prayer Room",
            occupancy_status="AVAILABLE",
            is_active=True
        ),
    ]

    for room in rooms:
        existing = Room.query.filter_by(
            room_number=room.room_number
        ).first()

        if not existing:
            db.session.add(room)

    # Save Roles and Rooms first to generate room IDs
    db.session.flush()

    # Seed Devices
    devices = [
        {
            "device_id": "DEV001",
            "room_number": "101",
            "device_code": "ESP32-001",
            "device_name": "Room 101 Sensor",
            "registration_status": "REGISTERED"
        },
        {
            "device_id": "DEV002",
            "room_number": "102",
            "device_code": "ESP32-002",
            "device_name": "Room 102 Sensor",
            "registration_status": "REGISTERED"
        },
        {
            "device_id": "DEV003",
            "room_number": "103",
            "device_code": "ESP32-003",
            "device_name": "Room 103 Sensor",
            "registration_status": "PENDING"
        },
        {
            "device_id": "DEV004",
            "room_number": "104",
            "device_code": "ESP32-004",
            "device_name": "Room 104 Sensor",
            "registration_status": "REGISTERED"
        },
        {
            "device_id": "DEV005",
            "room_number": "105",
            "device_code": "ESP32-005",
            "device_name": "Room 105 Sensor",
            "registration_status": "REGISTERED"
        },
        {
            "device_id": "DEV006",
            "room_number": "106",
            "device_code": "ESP32-006",
            "device_name": "Room 106 Sensor",
            "registration_status": "REGISTERED"
        },
        {
            "device_id": "DEV007",
            "room_number": "107",
            "device_code": "ESP32-007",
            "device_name": "Room 107 Sensor",
            "registration_status": "REGISTERED"
        },
    ]

    for data in devices:
        existing = Device.query.filter_by(
            device_id=data["device_id"]
        ).first()

        if not existing:
            room = Room.query.filter_by(
                room_number=data["room_number"]
            ).first()

            if room:
                device = Device(
                    device_id=data["device_id"],
                    room_id=room.room_id,
                    device_code=data["device_code"],
                    device_name=data["device_name"],
                    registration_status=data["registration_status"]
                )
                db.session.add(device)

    db.session.commit()
    print("Seed data inserted successfully!")


if __name__ == "__main__":
    seed_data()
