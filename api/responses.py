from flask import current_app, jsonify
from sqlalchemy.exc import IntegrityError

from database.extensions import db
from services.errors import (
    AssociationError,
    ConfigurationError,
    ConflictError,
    InactiveAccountError,
    InactiveDeviceError,
    InvalidCredentialsError,
    InvalidDeviceCredentialsError,
    InvalidReferenceError,
    NotFoundError,
    ServiceError,
)


def success_response(payload, status_code=200):
    """Return a JSON payload without changing its existing public shape."""
    return jsonify(payload), status_code


def error_response(message, status_code=400, **details):
    body = {"error": message}
    body.update(details)
    return jsonify(body), status_code


def database_error_response(operation, error, *, conflict_message=None):
    db.session.rollback()
    if isinstance(error, IntegrityError) and conflict_message:
        return error_response(conflict_message, 409)

    current_app.logger.error(
        "Database operation %s failed (%s)", operation, type(error).__name__
    )
    return error_response("Database operation failed", 500)


def unexpected_error_response(operation, error):
    db.session.rollback()
    current_app.logger.error(
        "Unexpected operation %s failed (%s)", operation, type(error).__name__
    )
    return error_response("Database operation failed", 500)


def service_error_response(error):
    status_codes = {
        NotFoundError: 404,
        ConflictError: 409,
        InvalidReferenceError: 400,
        AssociationError: 400,
        ConfigurationError: 500,
        InvalidCredentialsError: 401,
        InactiveAccountError: 403,
        InvalidDeviceCredentialsError: 401,
        InactiveDeviceError: 403,
    }
    if not isinstance(error, ServiceError):
        raise TypeError("error must be a ServiceError")
    return error_response(str(error), status_codes.get(type(error), 500), **error.details)
