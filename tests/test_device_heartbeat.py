import hashlib
from datetime import UTC, datetime, timedelta

from database.extensions import db
from database.models.device_status_log import DeviceStatusLog
from database.models.room import Room
from database.models.room_device import RoomDevice


def _register_device(
    app, *, device_id="HEARTBEAT-DEVICE", status="REGISTERED", room_active=True
):
    key = f"secret-{device_id}"
    with app.app_context():
        room = Room(
            room_number=f"{100 + db.session.query(Room).count()}",
            room_name="Heartbeat Test Room",
            occupancy_status="AVAILABLE",
            is_active=room_active,
        )
        db.session.add(room)
        db.session.flush()
        db.session.add(
            RoomDevice(
                device_id=device_id,
                room_id=room.room_id,
                device_code=f"CODE-{device_id}",
                registration_status=status,
                credential_hash=hashlib.sha256(key.encode("utf-8")).hexdigest(),
            )
        )
        db.session.commit()
    return key


def test_registered_device_heartbeat_sets_online_and_records_transition(
    app, unauthenticated_client
):
    key = _register_device(app)

    response = unauthenticated_client.post(
        "/api/device-monitoring/heartbeat",
        json={"device_id": "HEARTBEAT-DEVICE"},
        headers={"X-Device-Key": key},
    )

    assert response.status_code == 200
    assert response.json["current_status"] == "ONLINE"
    assert response.json["last_communication_at"]
    with app.app_context():
        device = db.session.get(RoomDevice, "HEARTBEAT-DEVICE")
        assert device.current_status == "ONLINE"
        assert device.last_communication_at is not None
        history = db.session.query(DeviceStatusLog).filter_by(
            device_id=device.device_id
        ).all()
        assert len(history) == 1
        assert history[0].previous_status == "UNKNOWN"
        assert history[0].new_status == "ONLINE"
        assert history[0].reason == "HEARTBEAT"


def test_repeated_online_heartbeats_do_not_duplicate_history(
    app, unauthenticated_client
):
    key = _register_device(app)
    headers = {"X-Device-Key": key}
    payload = {"device_id": "HEARTBEAT-DEVICE"}

    first = unauthenticated_client.post(
        "/api/device-monitoring/heartbeat", json=payload, headers=headers
    )
    second = unauthenticated_client.post(
        "/api/device-monitoring/heartbeat", json=payload, headers=headers
    )

    assert first.status_code == second.status_code == 200
    with app.app_context():
        assert db.session.query(DeviceStatusLog).filter_by(
            device_id="HEARTBEAT-DEVICE"
        ).count() == 1


def test_unknown_device_heartbeat_is_rejected(app, unauthenticated_client):
    response = unauthenticated_client.post(
        "/api/device-monitoring/heartbeat",
        json={"device_id": "UNKNOWN"},
        headers={"X-Device-Key": "unknown-secret"},
    )

    assert response.status_code == 401
    assert response.json == {"error": "Invalid device credentials"}


def test_inactive_device_and_inactive_room_heartbeats_are_rejected(
    app, unauthenticated_client
):
    pending_key = _register_device(app, device_id="PENDING-DEVICE", status="PENDING")
    inactive_room_key = _register_device(
        app, device_id="INACTIVE-ROOM-DEVICE", room_active=False
    )

    pending = unauthenticated_client.post(
        "/api/device-monitoring/heartbeat",
        json={"device_id": "PENDING-DEVICE"},
        headers={"X-Device-Key": pending_key},
    )
    inactive_room = unauthenticated_client.post(
        "/api/device-monitoring/heartbeat",
        json={"device_id": "INACTIVE-ROOM-DEVICE"},
        headers={"X-Device-Key": inactive_room_key},
    )

    assert pending.status_code == inactive_room.status_code == 403
    with app.app_context():
        assert db.session.get(RoomDevice, "PENDING-DEVICE").last_communication_at is None
        assert (
            db.session.get(RoomDevice, "INACTIVE-ROOM-DEVICE").last_communication_at
            is None
        )
        assert db.session.query(DeviceStatusLog).count() == 0


def test_offline_device_heartbeat_records_online_transition(
    app, unauthenticated_client
):
    key = _register_device(app, device_id="OFFLINE-DEVICE")
    with app.app_context():
        device = db.session.get(RoomDevice, "OFFLINE-DEVICE")
        device.current_status = "OFFLINE"
        db.session.commit()

    response = unauthenticated_client.post(
        "/api/device-monitoring/heartbeat",
        json={"device_id": "OFFLINE-DEVICE"},
        headers={"X-Device-Key": key},
    )

    assert response.status_code == 200
    with app.app_context():
        history = db.session.query(DeviceStatusLog).filter_by(
            device_id="OFFLINE-DEVICE"
        ).one()
        assert history.previous_status == "OFFLINE"
        assert history.new_status == "ONLINE"


def test_status_endpoints_return_current_status_and_history(app, client):
    key = _register_device(app, device_id="READ-DEVICE")
    heartbeat = client.post(
        "/api/device-monitoring/heartbeat",
        json={"device_id": "READ-DEVICE"},
        headers={"X-Device-Key": key},
    )
    assert heartbeat.status_code == 200

    current = client.get("/api/device-monitoring/devices/READ-DEVICE/status")
    history = client.get("/api/device-monitoring/devices/READ-DEVICE/history")
    all_statuses = client.get("/api/device-monitoring/devices/status")

    assert current.status_code == 200
    assert current.json["current_status"] == "ONLINE"
    assert history.status_code == 200
    assert len(history.json) == 1
    assert history.json[0]["reason"] == "HEARTBEAT"
    assert all_statuses.status_code == 200
    assert all_statuses.json[0]["device_id"] == "READ-DEVICE"


def test_dashboard_summary_separates_registered_and_online_counts(app, client):
    _register_device(app, device_id="SUMMARY-ONLINE")
    _register_device(app, device_id="SUMMARY-PENDING", status="PENDING")
    _register_device(app, device_id="SUMMARY-INACTIVE-ROOM", room_active=False)
    with app.app_context():
        device = db.session.get(RoomDevice, "SUMMARY-ONLINE")
        device.current_status = "ONLINE"
        db.session.commit()

    response = client.get("/api/device-monitoring/summary")

    assert response.status_code == 200
    assert response.json == {
        "registered_count": 2,
        "active_count": 1,
        "online_count": 1,
        "offline_count": 0,
        "unknown_count": 0,
    }


def test_reconciliation_marks_expired_online_device_offline(app):
    with app.app_context():
        room = Room(
            room_number="TIMEOUT-ROOM",
            room_name="Timeout Room",
            occupancy_status="AVAILABLE",
            is_active=True,
        )
        db.session.add(room)
        db.session.flush()
        db.session.add(
            RoomDevice(
                device_id="TIMEOUT-DEVICE",
                room_id=room.room_id,
                device_code="TIMEOUT-CODE",
                registration_status="REGISTERED",
                current_status="ONLINE",
                last_communication_at=datetime.now(UTC) - timedelta(seconds=121),
            )
        )
        db.session.commit()

    runner = app.test_cli_runner()
    result = runner.invoke(args=["reconcile-device-status"])

    assert result.exit_code == 0
    assert "Marked 1 device(s) offline" in result.output
    with app.app_context():
        device = db.session.get(RoomDevice, "TIMEOUT-DEVICE")
        assert device.current_status == "OFFLINE"
        entry = db.session.query(DeviceStatusLog).filter_by(
            device_id=device.device_id
        ).one()
        assert entry.previous_status == "ONLINE"
        assert entry.new_status == "OFFLINE"
        assert entry.reason == "HEARTBEAT_TIMEOUT"


def test_reconciliation_does_not_mark_fresh_device_offline(app):
    with app.app_context():
        room = Room(
            room_number="FRESH-ROOM",
            room_name="Fresh Room",
            occupancy_status="AVAILABLE",
            is_active=True,
        )
        db.session.add(room)
        db.session.flush()
        db.session.add(
            RoomDevice(
                device_id="FRESH-DEVICE",
                room_id=room.room_id,
                device_code="FRESH-CODE",
                registration_status="REGISTERED",
                current_status="ONLINE",
                last_communication_at=datetime.now(UTC) - timedelta(seconds=30),
            )
        )
        db.session.commit()

    result = app.test_cli_runner().invoke(args=["reconcile-device-status"])

    assert result.exit_code == 0
    assert "Marked 0 device(s) offline" in result.output
    with app.app_context():
        assert db.session.get(RoomDevice, "FRESH-DEVICE").current_status == "ONLINE"
        assert db.session.query(DeviceStatusLog).count() == 0


def test_reconciliation_uses_configured_heartbeat_timeout(app):
    app.config["DEVICE_HEARTBEAT_TIMEOUT_SECONDS"] = 3
    with app.app_context():
        room = Room(
            room_number="CONFIGURED-TIMEOUT-ROOM",
            room_name="Configured Timeout Room",
            occupancy_status="AVAILABLE",
            is_active=True,
        )
        db.session.add(room)
        db.session.flush()
        db.session.add(
            RoomDevice(
                device_id="CONFIGURED-TIMEOUT-DEVICE",
                room_id=room.room_id,
                device_code="CONFIGURED-TIMEOUT-CODE",
                registration_status="REGISTERED",
                current_status="ONLINE",
                last_communication_at=datetime.now(UTC) - timedelta(seconds=5),
            )
        )
        db.session.commit()

    result = app.test_cli_runner().invoke(args=["reconcile-device-status"])

    assert result.exit_code == 0
    assert "Marked 1 device(s) offline" in result.output
