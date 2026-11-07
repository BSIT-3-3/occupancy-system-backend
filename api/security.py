from datetime import UTC, datetime
from functools import wraps

from flask_jwt_extended import get_jwt_identity, jwt_required
from sqlalchemy.exc import SQLAlchemyError

from api.responses import database_error_response, error_response
from database.extensions import db, jwt
from database.models.refresh_token import RefreshToken
from database.models.user_session import UserSession
from services.authentication.user import get_user


@jwt.unauthorized_loader
def _missing_token(_reason):
    return error_response("Authentication required", 401)


@jwt.invalid_token_loader
def _invalid_token(_reason):
    return error_response("Invalid access token", 401)


@jwt.expired_token_loader
def _expired_token(_jwt_header, jwt_payload):
    if jwt_payload.get("type") == "refresh":
        return error_response("Refresh token has expired", 401)
    return error_response("Access token has expired", 401)


@jwt.revoked_token_loader
def _revoked_token(_jwt_header, jwt_payload):
    if jwt_payload.get("type") == "refresh":
        return error_response("Refresh token has been revoked", 401)
    return error_response("Access token has been revoked", 401)


@jwt.token_in_blocklist_loader
def _token_is_revoked(_jwt_header, jwt_payload):
    """Reject tokens whose backing session or refresh-token record is inactive."""
    try:
        session_id = int(jwt_payload.get("sid"))
        user_id = int(jwt_payload.get("sub"))
    except (TypeError, ValueError):
        return True

    session = db.session.get(UserSession, session_id)
    now = datetime.now(UTC)
    if (
        session is None
        or session.user_id != user_id
        or session.revoked_at is not None
        or _as_utc(session.expires_at) <= now
    ):
        return True

    if jwt_payload.get("type") == "access":
        return False
    if jwt_payload.get("type") != "refresh":
        return True

    token_record = db.session.query(RefreshToken).filter_by(
        jti=jwt_payload.get("jti")
    ).first()
    # Consumed refresh tokens reach the refresh route so reuse can revoke the
    # complete session. All other revoked states are rejected here.
    return (
        token_record is None
        or token_record.session_id != session_id
        or token_record.revoked_at is not None
    )


def _as_utc(value):
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def admin_required(view):
    @wraps(view)
    @jwt_required()
    def wrapped(*args, **kwargs):
        identity = get_jwt_identity()
        try:
            user_id = int(identity)
        except (TypeError, ValueError):
            return error_response("Invalid access token", 401)

        try:
            user = get_user(user_id)
            if user is None:
                return error_response("Authentication required", 401)
            if (user.status or "").upper() != "ACTIVE" or user.role is None:
                return error_response("Admin access required", 403)
            if user.role.role_name != "ADMIN":
                return error_response("Admin access required", 403)
        except SQLAlchemyError as error:
            return database_error_response("authorization.admin", error)

        return view(*args, **kwargs)

    return wrapped
