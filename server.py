from database import create_app
from flasgger import Swagger
import api.authentication.routes as routes_bp
from werkzeug.security import generate_password_hash

app = create_app()
app.register_blueprint(routes_bp.auth_bp)


swagger = Swagger(app)


hashed_password = generate_password_hash("Admin123!")
print("here" +hashed_password)

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
    return {"message": "API is running"}


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
    return {"status": "ok"}


if __name__ == "__main__":
    app.run(debug=True)