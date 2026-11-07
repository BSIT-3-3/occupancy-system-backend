from datetime import UTC, datetime, timedelta

from flask import current_app
from flask_jwt_extended import create_access_token, create_refresh_token
from flask_jwt_extended.utils import decode_token
from sqlalchemy.exc import SQLAlchemyError

from database.extensions import db
from database.models.refresh_token import RefreshToken
from database.models.user import User
from database.models.user_session import UserSession
from services.errors import InvalidRefreshTokenError


def _utc_now():
    return datetime.now(UTC)


def _as_utc(value):
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _as_timedelta(value):
    if isinstance(value, timedelta):
        return value
    return timedelta(seconds=value)


def _jwt_expiration(token):
    payload = decode_token(token)
    return payload["jti"], datetime.fromtimestamp(payload["exp"], UTC)


def _issue_token_pair(user, session, *, now=None):
    now = now or _utc_now()
    expires_at = _as_utc(session.expires_at)
    remaining_session = expires_at - now
    refresh_lifetime = _as_timedelta(
        current_app.config["JWT_REFRESH_TOKEN_EXPIRES"]
    )
    refresh_lifetime = min(refresh_lifetime, remaining_session)
    if refresh_lifetime.total_seconds() <= 0:
        raise InvalidRefreshTokenError("Invalid refresh token")

    claims = {"sid": session.session_id}
    access_token = create_access_token(
        identity=str(user.user_id), additional_claims=claims
    )
    refresh_token = create_refresh_token(
        identity=str(user.user_id),
        additional_claims=claims,
        expires_delta=refresh_lifetime,
    )
    jti, token_expires_at = _jwt_expiration(refresh_token)
    token_record = RefreshToken(
        session_id=session.session_id,
        jti=jti,
        expires_at=token_expires_at,
    )
    db.session.add(token_record)
    db.session.flush()

    session.last_seen_at = now
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "access_token_expires_in": int(
            _as_timedelta(current_app.config["JWT_ACCESS_TOKEN_EXPIRES"]).total_seconds()
        ),
        "refresh_token_expires_at": token_expires_at.isoformat(),
        "session_expires_at": expires_at.isoformat(),
        "refresh_token_record": token_record,
    }


def create_session_token_pair(user):
    """Create a session and its initial access and refresh tokens atomically."""
    try:
        now = _utc_now()
        session = UserSession(
            user_id=user.user_id,
            created_at=now,
            last_seen_at=now,
            expires_at=now
            + _as_timedelta(current_app.config["AUTH_SESSION_MAX_AGE"]),
        )
        db.session.add(session)
        db.session.flush()
        result = _issue_token_pair(user, session, now=now)
        db.session.commit()
        result.pop("refresh_token_record")
        return result
    except SQLAlchemyError:
        db.session.rollback()
        raise


def _revoke_session(session, *, now, reason):
    if session.revoked_at is None:
        session.revoked_at = now
        session.revoke_reason = reason
    db.session.query(RefreshToken).filter(
        RefreshToken.session_id == session.session_id,
        RefreshToken.revoked_at.is_(None),
    ).update({"revoked_at": now}, synchronize_session=False)


def rotate_refresh_token(claims):
    """Consume a refresh token once and atomically issue its successor."""
    try:
        token_record = (
            db.session.query(RefreshToken)
            .filter_by(jti=claims.get("jti"))
            .with_for_update()
            .first()
        )
        try:
            session_id = int(claims.get("sid"))
            user_id = int(claims.get("sub"))
        except (TypeError, ValueError):
            raise InvalidRefreshTokenError("Invalid refresh token") from None

        session = (
            db.session.query(UserSession)
            .filter_by(session_id=session_id)
            .with_for_update()
            .first()
        )
        now = _utc_now()

        if (
            token_record is None
            or session is None
            or token_record.session_id != session_id
            or session.user_id != user_id
        ):
            raise InvalidRefreshTokenError("Invalid refresh token")

        if token_record.consumed_at is not None:
            _revoke_session(session, now=now, reason="refresh_reuse")
            db.session.commit()
            raise InvalidRefreshTokenError("Invalid refresh token")

        if (
            token_record.revoked_at is not None
            or session.revoked_at is not None
            or _as_utc(session.expires_at) <= now
            or _as_utc(token_record.expires_at) <= now
        ):
            raise InvalidRefreshTokenError("Invalid refresh token")

        user = db.session.get(User, user_id)
        if (
            user is None
            or (user.status or "").upper() != "ACTIVE"
            or user.role is None
            or user.role.role_name != "ADMIN"
        ):
            _revoke_session(session, now=now, reason="account_unavailable")
            db.session.commit()
            raise InvalidRefreshTokenError("Invalid refresh token")

        token_record.consumed_at = now
        db.session.flush()
        result = _issue_token_pair(user, session, now=now)
        token_record.replaced_by_token_id = result["refresh_token_record"].refresh_token_id
        db.session.commit()
        result.pop("refresh_token_record")
        return result
    except SQLAlchemyError:
        db.session.rollback()
        raise


def revoke_session(session_id, user_id, *, reason="logout"):
    try:
        session = (
            db.session.query(UserSession)
            .filter_by(session_id=session_id, user_id=user_id)
            .with_for_update()
            .first()
        )
        if session is None:
            raise InvalidRefreshTokenError("Invalid session")
        _revoke_session(session, now=_utc_now(), reason=reason)
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        raise


def revoke_all_user_sessions(user_id):
    try:
        sessions = (
            db.session.query(UserSession)
            .filter_by(user_id=user_id)
            .with_for_update()
            .all()
        )
        now = _utc_now()
        session_ids = []
        for session in sessions:
            session_ids.append(session.session_id)
            if session.revoked_at is None:
                session.revoked_at = now
                session.revoke_reason = "logout_all"

        if session_ids:
            db.session.query(RefreshToken).filter(
                RefreshToken.session_id.in_(session_ids),
                RefreshToken.revoked_at.is_(None),
            ).update({"revoked_at": now}, synchronize_session=False)
        db.session.commit()
        return len(sessions)
    except SQLAlchemyError:
        db.session.rollback()
        raise
