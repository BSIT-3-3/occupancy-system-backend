from database.extensions import db
from database.models.role import Role


def test_role_crud_and_validation(client):
    invalid = client.post("/roles", json={"role_name": "  "})
    assert invalid.status_code == 400

    created = client.post("/roles", json={"role_name": "STAFF", "description": "Staff"})
    assert created.status_code == 201
    role_id = created.json["role_id"]

    assert client.get("/roles").json == [created.json]
    assert client.get(f"/roles/{role_id}").json == created.json

    updated = client.put(
        f"/roles/{role_id}", json={"role_name": "ADMIN", "description": None}
    )
    assert updated.status_code == 200
    assert updated.json["role_name"] == "ADMIN"
    assert updated.json["description"] is None
    assert client.put(f"/roles/{role_id}", json={"role_name": "x" * 51}).status_code == 400

    assert client.delete(f"/roles/{role_id}").json == {"message": "Role deleted"}


def test_role_unique_conflict_rolls_back(client, app):
    first = client.post("/roles", json={"role_name": "STAFF"})
    assert first.status_code == 201
    duplicate = client.post("/roles", json={"role_name": "STAFF"})
    assert duplicate.status_code == 409
    assert duplicate.json == {"error": "Role already exists"}

    with app.app_context():
        assert db.session.query(Role).filter_by(role_name="STAFF").count() == 1
