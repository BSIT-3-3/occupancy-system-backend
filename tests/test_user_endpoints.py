from werkzeug.security import check_password_hash

from database.extensions import db
from database.models.profile import UserProfile
from database.models.role import Role
from database.models.user import User


def test_create_and_read_user_never_exposes_password_hash(client, app):
    with app.app_context():
        role = Role(role_name="USER")
        db.session.add(role)
        db.session.commit()
        role_id = role.role_id

    response = client.post(
        "/users",
        json={
            "username": "alice",
            "password": "correct horse battery staple",
            "role_id": role_id,
        },
    )

    assert response.status_code == 201
    assert response.json == {
        "user_id": 1,
        "username": "alice",
        "full_name": None,
        "role_id": role_id,
        "status": "active",
    }
    assert "password" not in response.json

    with app.app_context():
        user = db.session.get(User, 1)
        assert check_password_hash(user.password, "correct horse battery staple")
        password_hash = user.password

    for path in ("/users", "/users/1"):
        result = client.get(path)
        assert result.status_code == 200
        assert "password" not in result.get_data(as_text=True)
        assert password_hash not in result.get_data(as_text=True)


def test_user_endpoints_validate_json_and_fields(client):
    assert client.post("/users", data="not-json").status_code == 400
    assert client.post("/users", json=[]).status_code == 400
    assert (
        client.post(
            "/users", json={"username": "alice", "password": "secret", "role_id": True}
        ).status_code
        == 400
    )
    assert (
        client.post(
            "/users",
            json={
                "username": "a" * 51,
                "password": "secret",
                "role_id": 1,
            },
        ).status_code
        == 400
    )


def test_update_and_delete_user_preserve_existing_endpoint_contract(client, app):
    with app.app_context():
        role = Role(role_name="USER")
        db.session.add(role)
        db.session.commit()
        role_id = role.role_id

    created = client.post(
        "/users",
        json={"username": "before", "password": "initial-password", "role_id": role_id},
    )
    assert created.status_code == 201
    user_id = created.json["user_id"]

    updated = client.put(
        f"/users/{user_id}",
        json={"username": "after", "password": "", "role_id": role_id},
    )
    assert updated.status_code == 200
    assert updated.json["username"] == "after"
    assert "password" not in updated.json
    assert client.put(f"/users/{user_id}", json=[]).status_code == 400

    deleted = client.delete(f"/users/{user_id}")
    assert deleted.status_code == 200
    assert deleted.json == {"message": "User deleted"}
    assert client.get(f"/users/{user_id}").status_code == 404


def test_user_database_failure_rolls_back_and_hides_exception(
    client, app, monkeypatch, caplog
):
    with app.app_context():
        role = Role(role_name="USER")
        db.session.add(role)
        db.session.commit()
        role_id = role.role_id

    from sqlalchemy.exc import SQLAlchemyError
    from sqlalchemy.orm import Session

    def fail_commit(_session):
        raise SQLAlchemyError("sensitive database statement details")

    monkeypatch.setattr(Session, "commit", fail_commit)
    response = client.post(
        "/users", json={"username": "alice", "password": "secret", "role_id": role_id}
    )

    assert response.status_code == 500
    assert response.json == {"error": "Database operation failed"}
    assert "sensitive database statement details" not in response.get_data(as_text=True)
    assert "sensitive database statement details" not in caplog.text

    monkeypatch.undo()
    assert client.get("/users").json == []


def test_registration_creates_user_and_profile_atomically(client, app, monkeypatch):
    with app.app_context():
        db.session.add(Role(role_name="USER"))
        db.session.commit()

    payload = {
        "username": "registered-user",
        "password": "secure-password",
        "first_name": "Reg",
        "last_name": "User",
    }
    response = client.post("/api/auth/register", json=payload)
    assert response.status_code == 201
    assert "password" not in response.get_data(as_text=True)

    with app.app_context():
        created = db.session.query(User).filter_by(username="registered-user").one()
        assert db.session.get(UserProfile, created.user_id) is not None

    # A failed commit must leave neither half of the registration behind.
    from sqlalchemy.exc import SQLAlchemyError
    from sqlalchemy.orm import Session

    def fail_commit(_session):
        raise SQLAlchemyError("sensitive database statement details")

    monkeypatch.setattr(Session, "commit", fail_commit)
    payload["username"] = "failed-registration"
    failed = client.post("/api/auth/register", json=payload)
    assert failed.status_code == 500
    assert "sensitive database statement details" not in failed.get_data(as_text=True)

    monkeypatch.undo()
    with app.app_context():
        assert (
            db.session.query(User).filter_by(username="failed-registration").count()
            == 0
        )
