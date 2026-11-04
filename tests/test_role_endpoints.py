from database.extensions import db
from database.models.role import Role


def test_role_api_only_exposes_the_admin_role(client, app):
    with app.app_context():
        db.session.add(Role(role_name="STAFF", description="Legacy role"))
        db.session.commit()

    roles = client.get("/roles")
    assert roles.status_code == 200
    assert len(roles.json) == 1
    assert roles.json[0]["role_name"] == "ADMIN"

    admin = roles.json[0]
    updated = client.put(
        f"/roles/{admin['role_id']}",
        json={"role_name": "ADMIN", "description": "Administrator"},
    )
    assert updated.status_code == 200
    assert updated.json["role_name"] == "ADMIN"

    rejected = client.post("/roles", json={"role_name": "STAFF"})
    assert rejected.status_code == 400
    assert rejected.json == {"error": "Only the ADMIN role is supported"}

    deleted = client.delete(f"/roles/{admin['role_id']}")
    assert deleted.status_code == 409
    assert deleted.json == {"error": "The ADMIN role cannot be deleted"}

    with app.app_context():
        assert db.session.query(Role).filter_by(role_name="STAFF").count() == 1
