from database import create_app
from flasgger import Swagger
import services.role.role as role_bp
import services.authentication.user as users_bp
import services.authentication.user_profile as users_profile_bp

app = create_app()
app.register_blueprint(role_bp.roles_bp)
app.register_blueprint(users_bp.users_bp)
app.register_blueprint(users_profile_bp.profiles_bp)

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