
from flasgger import Swagger

import api.authentication.routes as routes_bp
import services.authentication.user as users_bp
import services.authentication.user_profile as users_profile_bp
import services.role.role as role_bp

from database import create_app


app = create_app()

# Register Authentication API
app.register_blueprint(routes_bp.auth_bp)

# Register Role API
app.register_blueprint(role_bp.roles_bp)

# Register User API
app.register_blueprint(users_bp.users_bp)

# Register User Profile API
app.register_blueprint(users_profile_bp.profiles_bp)

# Initialize Swagger
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
