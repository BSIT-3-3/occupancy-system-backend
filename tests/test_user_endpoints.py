from werkzeug.security import check_password_hash

from database.extensions import db
from database.models.profile import UserProfile
from database.models.role import Role
from database.models.user import User


def test_create_and_read_user_never_exposes_password_hash(client, app):
    with app.app_context():
        role = db.session.query(Role).filter_by(role_name="ADMIN").one()
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
    user_id = response.json["user_id"]
    assert response.json == {
        "user_id": user_id,
        "username": "alice",
        "full_name": None,
        "role_id": role_id,
        "status": "active",
    }
    assert "password" not in response.json

    with app.app_context():
        user = db.session.get(User, user_id)
        assert check_password_hash(user.password, "correct horse battery staple")
        password_hash = user.password

    for path in ("/users", f"/users/{user_id}"):
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
        role = db.session.query(Role).filter_by(role_name="ADMIN").one()
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
        role = db.session.query(Role).filter_by(role_name="ADMIN").one()
        role_id = role.role_id

    from sqlalchemy.exc import SQLAlchemyError
    from sqlalchemy.orm import Session

    def fail_commit(_session):
        raise SQLAlchemyError("sensitive database statement details")

    monkeypatch.setattr(Session, "commit", fail_commit)
    response = client.post(
        "/users",
        json={
            "username": "alice",
            "password": "long-enough-secret",
            "role_id": role_id,
        },
    )

    assert response.status_code == 500
    assert response.json == {"error": "Database operation failed"}
    assert "sensitive database statement details" not in response.get_data(as_text=True)
    assert "sensitive database statement details" not in caplog.text

    monkeypatch.undo()
    assert [user["username"] for user in client.get("/users").json] == ["test-admin"]


def test_public_registration_creates_user_without_login_access(
    unauthenticated_client, app
):
    password = "secure-password-123"
    response = unauthenticated_client.post(
        "/api/auth/register",
        json={
            "username": "self-registered",
            "password": password,
            "first_name": "Self",
            "middle_name": "Test",
            "last_name": "Registered",
            "contact_number": "555-0100",
        },
    )
    assert response.status_code == 201
    assert response.json["message"] == "Registration successful"
    assert response.json["user"]["username"] == "self-registered"
    assert "password" not in response.get_data(as_text=True)
    assert password not in response.get_data(as_text=True)

    with app.app_context():
        user = db.session.query(User).filter_by(username="self-registered").one()
        assert user.role.role_name == "USER"
        assert check_password_hash(user.password, password)
        profile = db.session.get(UserProfile, user.user_id)
        assert profile.first_name == "Self"
        assert profile.middle_name == "Test"
        assert profile.last_name == "Registered"
        assert profile.contact_number == "555-0100"

    login = unauthenticated_client.post(
        "/api/auth/login",
        json={"username": "self-registered", "password": password},
    )
    assert login.status_code == 401
    assert login.json == {"error": "Invalid username or password"}


def test_public_registration_validates_fields_and_duplicate_username(
    unauthenticated_client,
):
    invalid = unauthenticated_client.post(
        "/api/auth/register",
        json={"username": "new-user", "password": "short"},
    )
    assert invalid.status_code == 400

    payload = {
        "username": "duplicate-user",
        "password": "registration-password",
        "first_name": "Duplicate",
        "last_name": "User",
    }
    assert (
        unauthenticated_client.post("/api/auth/register", json=payload).status_code
        == 201
    )
    duplicate = unauthenticated_client.post("/api/auth/register", json=payload)
    assert duplicate.status_code == 409
    assert duplicate.json == {"error": "Username already exists"}
