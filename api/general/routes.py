from flask import Blueprint

from api.responses import success_response

general_bp = Blueprint("general", __name__)


@general_bp.get("/")
def root():
    """
    API root endpoint.
    ---
    tags:
      - General
    responses:
      200:
        description: API is running
    """
    return success_response({"message": "API is running"})


@general_bp.get("/health")
def health():
    """
    Check API health.
    ---
    tags:
      - General
    responses:
      200:
        description: API is healthy
    """
    return success_response({"status": "ok"})
