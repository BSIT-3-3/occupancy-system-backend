from flask import request

from api.responses import error_response


def validate_json_request(required_fields):
    if not request.is_json:
        return None, error_response("Request must use JSON format", 400)

    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return None, error_response("Invalid JSON request body", 400)

    missing_fields = [
        field
        for field in required_fields
        if field not in data
        or data[field] is None
        or (isinstance(data[field], str) and not data[field].strip())
    ]

    if missing_fields:
        return None, error_response(
            "Missing required fields", 400, fields=missing_fields
        )

    return data, None


def validate_string_field(data, field):
    value = data.get(field)

    if not isinstance(value, str) or not value.strip():
        return None, error_response(f"{field} must be a non-empty string", 400)

    return value.strip(), None


def validate_optional_string_field(data, field, max_length, *, allow_empty=True):
    """Validate an optional string while preserving explicit null values."""
    if field not in data or data[field] is None:
        return data.get(field), None

    value = data[field]
    if not isinstance(value, str):
        return None, error_response(f"{field} must be a string", 400)

    value = value.strip()
    if not allow_empty and not value:
        return None, error_response(f"{field} must be a non-empty string", 400)
    if len(value) > max_length:
        return None, error_response(
            f"{field} must not exceed {max_length} characters", 400
        )

    return value, None


def validate_integer_field(data, field):
    value = data.get(field)
    if isinstance(value, bool) or not isinstance(value, int):
        return None, error_response(f"{field} must be an integer", 400)
    return value, None
