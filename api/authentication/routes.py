from flask import Blueprint, current_app, jsonify, request
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from werkzeug.security import check_password_hash

from api.authentication.validation import (
    validate_json_request,
    validate_string_field,
)
from database.extensions import db
from database.models.user import User
from services.authentication.user import register_user

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
        description: User login credentials
        schema:
          type: object
          required:
            - username
            - password
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
                  example: 1
                username:
                  type: string
                  example: admin
                full_name:
                  type: string
                  example: Juan Dela Cruz
                role_id:
                  type: integer
                  example: 1
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
    if not request.is_json:
        return jsonify({"error": "Request must use JSON format"}), 400

    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({"error": "Invalid JSON request body"}), 400

    username = data.get("username")
    password = data.get("password")

    if not isinstance(username, str) or not username.strip():
        return jsonify({"error": "Username is required"}), 400

    if not isinstance(password, str) or not password:
        return jsonify({"error": "Password is required"}), 400

    user = db.session.query(User).filter_by(username=username.strip()).first()

    if user is None or not check_password_hash(user.password, password):
        return jsonify({"error": "Invalid username or password"}), 401

    if user.status.upper() != "ACTIVE":
        return jsonify({"error": "Account is inactive"}), 403

    return jsonify(
        {
            "message": "Login successful",
            "user": {
                "user_id": user.user_id,
                "username": user.username,
                "full_name": user.full_name,
                "role_id": user.role_id,
                "status": user.status,
            },
        }
    ), 200

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
        description: User registration details
        schema:
          type: object
          required:
            - username
            - password
            - first_name
            - last_name
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
              example: John
            middle_name:
              type: string
              maxLength: 50
              example: Michael
            last_name:
              type: string
              maxLength: 50
              example: Doe
            contact_number:
              type: string
              maxLength: 20
              example: "09123456789"
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
                  example: 8
                username:
                  type: string
                  example: johndoe
                full_name:
                  type: string
                  example: John Michael Doe
                status:
                  type: string
                  example: ACTIVE
      400:
        description: Invalid request, missing fields, or invalid input
      409:
        description: Username already exists
      500:
        description: Default registration role is not configured
    """
    required_fields = [
        "username",
        "password",
        "first_name",
        "last_name",
    ]

    data, error = validate_json_request(required_fields)

    if error:
        return error

    # Validate required string fields
    for field in required_fields:
        value, error = validate_string_field(data, field)

        if error:
            return error

        data[field] = value

    # Validate optional fields
    for field in ["middle_name", "contact_number"]:
        if field in data and data[field] is not None:
            if not isinstance(data[field], str):
                return jsonify({
                    "error": f"{field} must be a string"
                }), 400

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
            return jsonify({
                "error": f"{field} must not exceed {limit} characters"
            }), 400

    if len(data["password"]) < 8:
        return jsonify({
            "error": "Password must be at least 8 characters"
        }), 400

    try:
        user, message, status_code = register_user(data)

        if message:
            return jsonify({"error": message}), status_code

        return jsonify({
            "message": "Registration successful",
            "user": user,
        }), status_code

    except IntegrityError:
        db.session.rollback()
        return jsonify({
            "error": "Username already exists"
        }), 409
    except SQLAlchemyError as error:
        db.session.rollback()
        current_app.logger.error(
            "Database operation registration failed (%s)", type(error).__name__
        )
        return jsonify({"error": "Database operation failed"}), 500
    except (KeyError, TypeError, ValueError) as error:
        db.session.rollback()
        current_app.logger.error(
            "Unexpected registration failure (%s)", type(error).__name__
        )
        return jsonify({"error": "Registration failed"}), 500
