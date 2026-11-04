from flask import Blueprint, current_app
from flask_jwt_extended import create_access_token
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
from database.extensions import db
from services.authentication.auth import authenticate_user
from services.authentication.user import register_user
from services.errors import ServiceError

auth_bp = Blueprint("authentication", __name__, url_prefix="/api/auth")


@auth_bp.get("/verify")
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
        description: Login successful; includes a bearer access token
      400:
        description: Invalid request or missing credentials
      401:
        description: Invalid username or password
      403:
        description: Account is inactive
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

    token = create_access_token(identity=str(user.user_id))
    return success_response(
        {
            "message": "Login successful",
            "access_token": token,
            "user": user.to_dict(),
        }
    )


@auth_bp.post("/register")
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
