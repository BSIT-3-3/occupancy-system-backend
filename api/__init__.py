from api.authentication.routes import auth_bp
from api.occupancy.routes import occupancy_bp
from api.profiles.routes import profiles_bp
from api.roles.routes import roles_bp
from api.users.routes import users_bp


def register_blueprints(app):
    """Register all feature APIs in one place."""
    for blueprint in (auth_bp, users_bp, profiles_bp, roles_bp, occupancy_bp):
        app.register_blueprint(blueprint)
