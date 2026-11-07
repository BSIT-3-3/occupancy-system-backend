from database.extensions import db
from database.models.refresh_token import RefreshToken
from database.models.user_session import UserSession


def _login(client):
    response = client.post(
        "/api/auth/login",
        json={"username": "test-admin", "password": "test-admin-password-123"},
    )
    assert response.status_code == 200
    return response.json


def test_login_creates_session_and_refresh_token(unauthenticated_client, app):
    tokens = _login(unauthenticated_client)

    assert tokens["access_token"]
    assert tokens["refresh_token"]
    assert tokens["access_token_expires_in"] == 900

    with app.app_context():
        session = db.session.query(UserSession).one()
        refresh_token = db.session.query(RefreshToken).one()
        assert session.user_id == app.config["TEST_ADMIN_ID"]
        assert session.revoked_at is None
        assert session.expires_at is not None
        assert refresh_token.session_id == session.session_id
        assert refresh_token.consumed_at is None


def test_refresh_rotates_token_and_links_its_successor(unauthenticated_client, app):
    original = _login(unauthenticated_client)
    rotated = unauthenticated_client.post(
        "/api/auth/refresh",
        headers={"Authorization": f"Bearer {original['refresh_token']}"},
    )

    assert rotated.status_code == 200
    assert rotated.json["access_token"] != original["access_token"]
    assert rotated.json["refresh_token"] != original["refresh_token"]

    with app.app_context():
        records = db.session.query(RefreshToken).order_by(
            RefreshToken.refresh_token_id
        ).all()
        assert len(records) == 2
        assert records[0].consumed_at is not None
        assert records[0].replaced_by_token_id == records[1].refresh_token_id
        assert records[1].consumed_at is None

    protected = unauthenticated_client.get(
        "/users",
        headers={"Authorization": f"Bearer {rotated.json['access_token']}"},
    )
    assert protected.status_code == 200


def test_refresh_token_reuse_revokes_the_session(unauthenticated_client, app):
    original = _login(unauthenticated_client)
    rotated = unauthenticated_client.post(
        "/api/auth/refresh",
        headers={"Authorization": f"Bearer {original['refresh_token']}"},
    )
    assert rotated.status_code == 200

    replay = unauthenticated_client.post(
        "/api/auth/refresh",
        headers={"Authorization": f"Bearer {original['refresh_token']}"},
    )
    assert replay.status_code == 401
    assert replay.json == {"error": "Invalid refresh token"}

    with app.app_context():
        session = db.session.query(UserSession).one()
        assert session.revoked_at is not None
        assert session.revoke_reason == "refresh_reuse"
        assert all(
            token.revoked_at is not None
            for token in db.session.query(RefreshToken).all()
        )

    protected = unauthenticated_client.get(
        "/users",
        headers={"Authorization": f"Bearer {rotated.json['access_token']}"},
    )
    assert protected.status_code == 401

    latest_refresh = unauthenticated_client.post(
        "/api/auth/refresh",
        headers={"Authorization": f"Bearer {rotated.json['refresh_token']}"},
    )
    assert latest_refresh.status_code == 401


def test_logout_revokes_current_access_and_refresh_tokens(unauthenticated_client):
    tokens = _login(unauthenticated_client)
    logout = unauthenticated_client.post(
        "/api/auth/logout",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert logout.status_code == 200

    protected = unauthenticated_client.get(
        "/users", headers={"Authorization": f"Bearer {tokens['access_token']}"}
    )
    assert protected.status_code == 401

    refresh = unauthenticated_client.post(
        "/api/auth/refresh",
        headers={"Authorization": f"Bearer {tokens['refresh_token']}"},
    )
    assert refresh.status_code == 401


def test_logout_all_revokes_every_session_for_the_user(unauthenticated_client, app):
    first = _login(unauthenticated_client)
    second = _login(unauthenticated_client)

    logout_all = unauthenticated_client.post(
        "/api/auth/logout-all",
        headers={"Authorization": f"Bearer {first['access_token']}"},
    )
    assert logout_all.status_code == 200
    assert logout_all.json["revoked_sessions"] == 2

    with app.app_context():
        sessions = db.session.query(UserSession).all()
        assert len(sessions) == 2
        assert all(session.revoked_at is not None for session in sessions)

    for token in (first["access_token"], second["access_token"]):
        response = unauthenticated_client.get(
            "/users", headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 401

    for token in (first["refresh_token"], second["refresh_token"]):
        response = unauthenticated_client.post(
            "/api/auth/refresh", headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 401
