from flasgger import Swagger

from api import register_blueprints
from api.responses import success_response
from database import create_app

app = create_app()
register_blueprints(app)

swagger = Swagger(app)


@app.get("/")
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


@app.get("/health")
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


if __name__ == "__main__":
    app.run(debug=True)
