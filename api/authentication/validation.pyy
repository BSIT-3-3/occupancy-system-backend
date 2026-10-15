from flask import jsonify, request


def validate_json_request(required_fields):
    if not request.is_json:
        return None, (
            jsonify({"error": "Request must use JSON format"}),
            400
        )

    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return None, (
            jsonify({"error": "Invalid JSON request body"}),
            400
        )

    missing_fields = [
        field for field in required_fields
        if field not in data
        or data[field] is None
        or (
            isinstance(data[field], str)
            and not data[field].strip()
        )
    ]

    if missing_fields:
        return None, (
            jsonify({
                "error": "Missing required fields",
                "fields": missing_fields
            }),
            400
        )

    return data, None


def validate_string_field(data, field):
    value = data.get(field)

    if not isinstance(value, str) or not value.strip():
        return None, (
            jsonify({
                "error": f"{field} must be a non-empty string"
            }),
            400
        )

    return value.strip(), None
