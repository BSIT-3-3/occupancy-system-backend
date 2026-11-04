from database.extensions import db
from database.models.profile import UserProfile
from database.models.role import Role
from database.models.user import User


def _create_user(app):
    with app.app_context():
        role = db.session.query(Role).filter_by(role_name="ADMIN").one()
        user = User(
            username="profile-user", password="not-a-real-hash", role_id=role.role_id
        )
        db.session.add(user)
        db.session.commit()
        return user.user_id


def test_profile_create_read_and_update(client, app):
    user_id = _create_user(app)
    payload = {
        "user_id": user_id,
        "first_name": "Ada",
        "middle_name": "M",
        "last_name": "Lovelace",
        "contact_number": "12345",
    }
    created = client.post("/user_profiles", json=payload)
    assert created.status_code == 201
    assert created.json == payload

    assert client.get(f"/user_profiles/{user_id}").json == payload
    assert client.get("/user_profiles").json == [payload]

    updated = client.put(
        f"/user_profiles/{user_id}",
        json={"first_name": "Augusta", "last_name": "Lovelace"},
    )
    assert updated.status_code == 200
    assert updated.json["first_name"] == "Augusta"
    assert updated.json["middle_name"] is None

    with app.app_context():
        assert db.session.get(UserProfile, user_id).first_name == "Augusta"


def test_profile_validation_and_duplicate_conflict(client, app):
    user_id = _create_user(app)
    assert client.post("/user_profiles", json=[]).status_code == 400
    assert (
        client.post(
            "/user_profiles",
            json={"user_id": True, "first_name": "Ada", "last_name": "Lovelace"},
        ).status_code
        == 400
    )

    payload = {"user_id": user_id, "first_name": "Ada", "last_name": "Lovelace"}
    assert client.post("/user_profiles", json=payload).status_code == 201
    duplicate = client.post("/user_profiles", json=payload)
    assert duplicate.status_code == 409
    assert duplicate.json == {"error": "Profile already exists for this user"}
