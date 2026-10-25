from flask import Blueprint, jsonify, request
from werkzeug.security import check_password_hash

from database.extensions import db
from database.models.user import User

auth_bp = Blueprint(
    "authentication",
    __name__,
    url_prefix="/api/auth"
)


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
        return jsonify({
            "error": "Request must use JSON format"
        }), 400

    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({
            "error": "Invalid JSON request body"
        }), 400

    username = data.get("username")
    password = data.get("password")

    if not isinstance(username, str) or not username.strip():
        return jsonify({
            "error": "Username is required"
        }), 400

    if not isinstance(password, str) or not password:
        return jsonify({
            "error": "Password is required"
        }), 400

    user = db.session.query(User).filter_by(
        username=username.strip()
    ).first()

    if user is None or not check_password_hash(
        user.password, password
    ):
        return jsonify({
            "error": "Invalid username or password"
        }), 401

    if user.status.upper() != "ACTIVE":
        return jsonify({
            "error": "Account is inactive"
        }), 403

    return jsonify({
        "message": "Login successful",
        "user": {
            "user_id": user.user_id,
            "username": user.username,
            "full_name": user.full_name,
            "role_id": user.role_id,
            "status": user.status
        }
    }), 200