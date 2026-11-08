from flask import Blueprint, current_app
from flask_jwt_extended import get_jwt, get_jwt_identity, jwt_required
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from api.authentication.validation import (
    validate_json_request,
    validate_optional_string_field,
    validate_string_field,
)
from api.responses import (
    database_error_response,
    error_response,
    service_error_response,
    success_response,
)
from api.security import admin_required
from database.extensions import db, limiter
from services.authentication.auth import authenticate_user
from services.authentication.tokens import (
    create_session_token_pair,
    revoke_all_user_sessions,
    revoke_session,
    rotate_refresh_token,
)
from services.authentication.user import register_user
from services.errors import ServiceError
from services.security.rate_limits import (
    AUTH_LOGIN,
    AUTH_REFRESH,
    AUTH_REGISTER,
    READ,
    WRITE,
)

auth_bp = Blueprint("authentication", __name__, url_prefix="/api/auth")


@auth_bp.get("/verify")
@limiter.limit(READ)
@admin_required
def verify_token():
    """Verify that the bearer token belongs to an active administrator.
    ---
    tags:
      - Authentication
    security:
      - Bearer: []
    responses:
      200:
        description: Token is valid for an active administrator
        schema:
          type: object
          properties:
            valid:
              type: boolean
              example: true
      401:
        description: Token is missing, invalid, or expired
      403:
        description: Token is valid but the account is not an active administrator
    """
    return success_response({"valid": True})


@auth_bp.post("/login")
@limiter.limit(AUTH_LOGIN)
def login():
    """
    Authenticate an admin account.
    ---
    tags:
      - Authentication
    consumes:
      - application/json
    produces:
      - application/json
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required: [username, password]
          properties:
            username:
              type: string
              example: admin
            password:
              type: string
              example: CorrectHorseBatteryStaple
    responses:
      200:
        description: Login successful; includes access and refresh bearer tokens
        schema:
          type: object
          properties:
            access_token:
              type: string
            refresh_token:
              type: string
            access_token_expires_in:
              type: integer
            refresh_token_expires_at:
              type: string
              format: date-time
            session_expires_at:
              type: string
              format: date-time
            user:
              type: object
      400:
        description: Invalid request or missing credentials
      401:
        description: Invalid username or password
      403:
        description: Account is inactive
      500:
        description: Login could not be completed
    """
    data, error = validate_json_request([])
    if error:
        return error

    username = data.get("username")
    if not isinstance(username, str) or not username.strip():
        return error_response("Username is required", 400)
    password = data.get("password")
    if not isinstance(password, str) or not password:
        return error_response("Password is required", 400)

    try:
        user = authenticate_user(username.strip(), password)
    except ServiceError as error:
        return service_error_response(error)
    except SQLAlchemyError as error:
        db.session.rollback()
        current_app.logger.error(
            "Database operation authentication.login failed (%s)",
            type(error).__name__,
        )
        return error_response("Database operation failed", 500)

    try:
        tokens = create_session_token_pair(user)
    except SQLAlchemyError as error:
        db.session.rollback()
        current_app.logger.error(
            "Database operation authentication.login failed (%s)",
            type(error).__name__,
        )
        return error_response("Database operation failed", 500)

    return success_response(
        {
            "message": "Login successful",
            **tokens,
            "user": user.to_dict(),
        }
    )


@auth_bp.post("/refresh")
@limiter.limit(AUTH_REFRESH)
@jwt_required(refresh=True)
def refresh():
    """Rotate a refresh token and issue a new access/refresh pair.
    ---
    tags:
      - Authentication
    security:
      - Bearer: []
    responses:
      200:
        description: Refresh token rotated successfully
        schema:
          type: object
          properties:
            access_token:
              type: string
            refresh_token:
              type: string
            access_token_expires_in:
              type: integer
            refresh_token_expires_at:
              type: string
              format: date-time
            session_expires_at:
              type: string
              format: date-time
      401:
        description: Refresh token is invalid, expired, revoked, or reused
      500:
        description: Token rotation could not be completed
    """
    try:
        tokens = rotate_refresh_token(get_jwt())
    except ServiceError as error:
        return service_error_response(error)
    except SQLAlchemyError as error:
        return database_error_response("authentication.refresh", error)

    return success_response({"message": "Token refreshed", **tokens})


@auth_bp.post("/logout")
@limiter.limit(WRITE)
@admin_required
def logout():
    """Revoke the current login session.
    ---
    tags:
      - Authentication
    security:
      - Bearer: []
    responses:
      200:
        description: Current session revoked
      401:
        description: Access token is missing, invalid, expired, or revoked
      500:
        description: Session revocation could not be completed
    """
    claims = get_jwt()
    try:
        revoke_session(int(claims["sid"]), int(get_jwt_identity()))
    except (KeyError, TypeError, ValueError):
        return error_response("Invalid access token", 401)
    except ServiceError as error:
        return service_error_response(error)
    except SQLAlchemyError as error:
        return database_error_response("authentication.logout", error)

    return success_response({"message": "Logged out"})


@auth_bp.post("/logout-all")
@limiter.limit(WRITE)
@admin_required
def logout_all():
    """Revoke every login session belonging to the current user.
    ---
    tags:
      - Authentication
    security:
      - Bearer: []
    responses:
      200:
        description: All sessions revoked
        schema:
          type: object
          properties:
            revoked_sessions:
              type: integer
      401:
        description: Access token is missing, invalid, expired, or revoked
      500:
        description: Session revocation could not be completed
    """
    try:
        user_id = int(get_jwt_identity())
        revoked_count = revoke_all_user_sessions(user_id)
    except (TypeError, ValueError):
        return error_response("Invalid access token", 401)
    except SQLAlchemyError as error:
        return database_error_response("authentication.logout_all", error)

    return success_response(
        {"message": "All sessions logged out", "revoked_sessions": revoked_count}
    )


@auth_bp.post("/register")
@limiter.limit(AUTH_REGISTER)
def register():
    """Register a public non-admin user and profile.
    ---
    tags:
      - Authentication
    consumes:
      - application/json
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required: [username, password, first_name, last_name]
          properties:
            username:
              type: string
              maxLength: 50
            password:
              type: string
              minLength: 8
            first_name:
              type: string
              maxLength: 50
            middle_name:
              type: string
              maxLength: 50
            last_name:
              type: string
              maxLength: 50
            contact_number:
              type: string
              maxLength: 20
    responses:
      201:
        description: Registration successful; account cannot log in
      400:
        description: Invalid request or field values
      409:
        description: Username already exists
      500:
        description: Registration failed
    """
    required_fields = ["username", "password", "first_name", "last_name"]
    data, error = validate_json_request(required_fields)
    if error:
        return error

    for field in required_fields:
        data[field], error = validate_string_field(data, field)
        if error:
            return error

    if len(data["username"]) > 50:
        return error_response("username must not exceed 50 characters", 400)
    if len(data["password"]) < 8:
        return error_response("Password must be at least 8 characters", 400)

    for field, limit in (("first_name", 50), ("last_name", 50)):
        if len(data[field]) > limit:
            return error_response(f"{field} must not exceed {limit} characters", 400)

    for field, limit in (("middle_name", 50), ("contact_number", 20)):
        data[field], error = validate_optional_string_field(
            data, field, limit, allow_empty=True
        )
        if error:
            return error

    try:
        user = register_user(data)
    except ServiceError as error:
        return service_error_response(error)
    except IntegrityError as error:
        return database_error_response(
            "authentication.register", error, conflict_message="Username already exists"
        )
    except SQLAlchemyError as error:
        return database_error_response("authentication.register", error)

    return success_response(
        {
            "message": "Registration successful",
            "user": {
                "user_id": user.user_id,
                "username": user.username,
                "full_name": user.full_name,
                "status": user.status,
            },
        },
        201,
    )
