from datetime import timedelta

from flask_jwt_extended import create_access_token
from werkzeug.security import generate_password_hash

from database.extensions import db
from database.models.role import Role
from database.models.user import User


def test_admin_login_returns_bearer_token(client, unauthenticated_client):
    response = unauthenticated_client.post(
        "/api/auth/login",
        json={"username": "test-admin", "password": "test-admin-password-123"},
    )
    assert response.status_code == 200
    assert response.json["message"] == "Login successful"
    assert response.json["user"]["username"] == "test-admin"
    assert response.json["access_token"]

    protected = unauthenticated_client.get(
        "/users",
        headers={"Authorization": f"Bearer {response.json['access_token']}"},
    )
    assert protected.status_code == 200


def test_verify_endpoint_checks_bearer_token(client, unauthenticated_client):
    valid = client.get("/api/auth/verify")
    assert valid.status_code == 200
    assert valid.json == {"valid": True}

    missing = unauthenticated_client.get("/api/auth/verify")
    assert missing.status_code == 401
    assert missing.json == {"error": "Authentication required"}

    invalid = unauthenticated_client.get(
        "/api/auth/verify", headers={"Authorization": "Bearer invalid.token"}
    )
    assert invalid.status_code == 401
    assert invalid.json == {"error": "Invalid access token"}


def test_admin_endpoints_require_a_valid_unexpired_token(app, unauthenticated_client):
    missing = unauthenticated_client.get("/users")
    assert missing.status_code == 401
    assert missing.json == {"error": "Authentication required"}

    invalid = unauthenticated_client.get(
        "/roles", headers={"Authorization": "Bearer invalid.token.value"}
    )
    assert invalid.status_code == 401
    assert invalid.json == {"error": "Invalid access token"}

    with app.app_context():
        expired = create_access_token(
            identity=str(app.config["TEST_ADMIN_ID"]),
            expires_delta=timedelta(seconds=-1),
        )
    expired_response = unauthenticated_client.get(
        "/user_profiles",
        headers={"Authorization": f"Bearer {expired}"},
    )
    assert expired_response.status_code == 401
    assert expired_response.json == {"error": "Access token has expired"}


def test_only_active_admin_accounts_can_login(app, unauthenticated_client):
    with app.app_context():
        staff = Role(role_name="STAFF", description="Legacy role")
        db.session.add(staff)
        db.session.flush()
        admin_role = db.session.query(Role).filter_by(role_name="ADMIN").one()
        db.session.add(
            User(
                username="legacy-staff",
                password=generate_password_hash("legacy-password-123"),
                role_id=staff.role_id,
                status="ACTIVE",
            )
        )
        inactive = User(
            username="inactive-admin",
            password=generate_password_hash("inactive-password-123"),
            role_id=admin_role.role_id,
            status="INACTIVE",
        )
        db.session.add(inactive)
        db.session.commit()

    non_admin = unauthenticated_client.post(
        "/api/auth/login",
        json={"username": "legacy-staff", "password": "legacy-password-123"},
    )
    assert non_admin.status_code == 401
    assert non_admin.json == {"error": "Invalid username or password"}

    inactive = unauthenticated_client.post(
        "/api/auth/login",
        json={"username": "inactive-admin", "password": "inactive-password-123"},
    )
    assert inactive.status_code == 403
    assert inactive.json == {"error": "Account is inactive"}

    with app.app_context():
        staff_user = db.session.query(User).filter_by(username="legacy-staff").one()
        staff_token = create_access_token(identity=str(staff_user.user_id))

    forbidden = unauthenticated_client.get(
        "/users", headers={"Authorization": f"Bearer {staff_token}"}
    )
    assert forbidden.status_code == 403
    assert forbidden.json == {"error": "Admin access required"}


def test_admin_bootstrap_is_operator_only_and_hashes_password(app):
    runner = app.test_cli_runner()
    result = runner.invoke(
        args=["create-admin", "--username", "bootstrapped-admin"],
        input="long-bootstrap-password-123!\nlong-bootstrap-password-123!\n",
    )
    assert result.exit_code == 0
    assert result.output.strip().endswith("Admin account created.")

    with app.app_context():
        user = db.session.query(User).filter_by(username="bootstrapped-admin").one()
        assert user.role.role_name == "ADMIN"
        assert user.password != "long-bootstrap-password-123!"
