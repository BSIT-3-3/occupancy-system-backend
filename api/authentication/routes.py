from flask import Blueprint, current_app
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from api.authentication.validation import validate_json_request, validate_string_field
from api.responses import error_response, service_error_response, success_response
from database.extensions import db
from services.authentication.auth import authenticate_user
from services.authentication.user import register_user
from services.errors import ServiceError

auth_bp = Blueprint("authentication", __name__, url_prefix="/api/auth")


@auth_bp.post("/login")
def login():
    """
    Authenticate a user.
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
              example: Admin123!
    responses:
      200:
        description: Login successful
        schema:
          type: object
          properties:
            message:
              type: string
              example: Login successful
            user:
              type: object
              properties:
                user_id:
                  type: integer
                username:
                  type: string
                full_name:
                  type: string
                  nullable: true
                role_id:
                  type: integer
                status:
                  type: string
                  example: ACTIVE
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
    username = username.strip()
    password = data.get("password")
    if not isinstance(password, str) or not password:
        return error_response("Password is required", 400)

    try:
        user = authenticate_user(username, password)
    except ServiceError as error:
        return service_error_response(error)
    except SQLAlchemyError as error:
        db.session.rollback()
        current_app.logger.error(
            "Database operation authentication.login failed (%s)",
            type(error).__name__,
        )
        return error_response("Database operation failed", 500)

    return success_response({"message": "Login successful", "user": user.to_dict()})


@auth_bp.post("/register")
def register():
    """
    Register a new user.
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
          required: [username, password, first_name, last_name]
          properties:
            username:
              type: string
              maxLength: 50
              example: johndoe
            password:
              type: string
              minLength: 8
              example: SecurePassword123!
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
        description: Registration successful
        schema:
          type: object
          properties:
            message:
              type: string
              example: Registration successful
            user:
              type: object
              properties:
                user_id:
                  type: integer
                username:
                  type: string
                full_name:
                  type: string
                status:
                  type: string
                  example: ACTIVE
      400:
        description: Invalid request, missing fields, or invalid input
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
        value, error = validate_string_field(data, field)
        if error:
            return error
        data[field] = value

    for field in ("middle_name", "contact_number"):
        if field in data and data[field] is not None:
            if not isinstance(data[field], str):
                return error_response(f"{field} must be a string", 400)
            data[field] = data[field].strip()

    limits = {
        "username": 50,
        "first_name": 50,
        "middle_name": 50,
        "last_name": 50,
        "contact_number": 20,
    }
    
    for field, limit in limits.items():
        if len(data.get(field) or "") > limit:
            return error_response(
                f"{field} must not exceed {limit} characters", 400
            )
    if len(data["password"]) < 8:
        return error_response("Password must be at least 8 characters", 400)

    try:
        user = register_user(data)
    except ServiceError as error:
        return service_error_response(error)
    except IntegrityError:
        db.session.rollback()
        return error_response("Username already exists", 409)
    except SQLAlchemyError as error:
        db.session.rollback()
        current_app.logger.error(
            "Database operation registration failed (%s)", type(error).__name__
        )
        return error_response("Database operation failed", 500)
    except (KeyError, TypeError, ValueError) as error:
        db.session.rollback()
        current_app.logger.error(
            "Unexpected registration failure (%s)", type(error).__name__
        )
        return error_response("Registration failed", 500)

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
