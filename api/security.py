from functools import wraps

from flask_jwt_extended import get_jwt_identity, jwt_required
from sqlalchemy.exc import SQLAlchemyError

from api.responses import database_error_response, error_response
from database.extensions import jwt
from services.authentication.user import get_user


@jwt.unauthorized_loader
def _missing_token(_reason):
    return error_response("Authentication required", 401)


@jwt.invalid_token_loader
def _invalid_token(_reason):
    return error_response("Invalid access token", 401)


@jwt.expired_token_loader
def _expired_token(_jwt_header, _jwt_payload):
    return error_response("Access token has expired", 401)


@jwt.revoked_token_loader
def _revoked_token(_jwt_header, _jwt_payload):
    return error_response("Access token has been revoked", 401)


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
