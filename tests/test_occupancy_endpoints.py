def create_event(client, occupancy_data):
    return client.post(
        "/api/occupancy/events",
        json={
            "room_id": occupancy_data["room_id"],
            "device_id": occupancy_data["device_id"],
            "event_type": "MOTION_DETECTED",
            "occupancy_status": "OCCUPIED",
        },
        headers={
            "X-Device-Key": occupancy_data["device_key"],
        },
    )


def test_create_occupancy_event(client, occupancy_data):
    response = create_event(client, occupancy_data)

    assert response.status_code == 201

    data = response.get_json()

    assert data["event"]["occupancy_status"] == "OCCUPIED"


def test_create_event_missing_fields(client):
    response = client.post("/api/occupancy/events", json={})

    assert response.status_code == 400


def test_create_event_invalid_status(client, occupancy_data):
    response = client.post(
        "/api/occupancy/events",
        json={
            "room_id": occupancy_data["room_id"],
            "device_id": occupancy_data["device_id"],
            "event_type": "MOTION_DETECTED",
            "occupancy_status": "INVALID",
        },
        headers={
            "X-Device-Key": occupancy_data["device_key"],
        },
    )

    assert response.status_code == 400


def test_create_event_room_not_found(client, occupancy_data):
    response = client.post(
        "/api/occupancy/events",
        json={
            "room_id": 999,
            "device_id": occupancy_data["device_id"],
            "event_type": "MOTION_DETECTED",
            "occupancy_status": "OCCUPIED",
        },
        headers={
            "X-Device-Key": occupancy_data["device_key"],
        },
    )

    assert response.status_code == 404


def test_create_event_device_not_found(client, occupancy_data):
    response = client.post(
        "/api/occupancy/events",
        json={
            "room_id": occupancy_data["room_id"],
            "device_id": "UNKNOWN-DEVICE",
            "event_type": "MOTION_DETECTED",
            "occupancy_status": "OCCUPIED",
        },
        headers={
            "X-Device-Key": occupancy_data["device_key"],
        },
    )

    assert response.status_code == 401


def test_get_all_occupancy_events(client, occupancy_data):
    create_event(client, occupancy_data)

    response = client.get("/api/occupancy/events")

    assert response.status_code == 200
    assert response.get_json()["count"] == 1


def test_get_occupancy_event_by_id(client, occupancy_data):
    create_event(client, occupancy_data)

    response = client.get("/api/occupancy/events/1")

    assert response.status_code == 200
    assert response.get_json()["event"]["event_type"] == "MOTION_DETECTED"


def test_get_nonexistent_occupancy_event(client):
    response = client.get("/api/occupancy/events/999")

    assert response.status_code == 404


def test_update_occupancy_event(client, occupancy_data):
    create_event(client, occupancy_data)

    response = client.put(
        "/api/occupancy/events/1",
        json={
            "event_type": "MANUAL_UPDATE",
            "occupancy_status": "AVAILABLE",
        },
    )

    assert response.status_code == 200
    assert response.get_json()["event"]["event_type"] == "MANUAL_UPDATE"
    assert response.get_json()["event"]["occupancy_status"] == "AVAILABLE"


def test_update_invalid_occupancy_status(client, occupancy_data):
    create_event(client, occupancy_data)

    response = client.put(
        "/api/occupancy/events/1",
        json={
            "occupancy_status": "INVALID",
        },
    )

    assert response.status_code == 400


def test_update_nonexistent_event(client):
    response = client.put(
        "/api/occupancy/events/999",
        json={"event_type": "UPDATED"},
    )

    assert response.status_code == 404


def test_delete_occupancy_event(client, occupancy_data):
    create_event(client, occupancy_data)

    response = client.delete("/api/occupancy/events/1")

    assert response.status_code == 200

    get_response = client.get("/api/occupancy/events/1")

    assert get_response.status_code == 404


def test_delete_nonexistent_event(client):
    response = client.delete("/api/occupancy/events/999")

    assert response.status_code == 404
