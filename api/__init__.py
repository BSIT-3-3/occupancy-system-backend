from api.assistance.routes import assistance_bp
from api.authentication.routes import auth_bp
from api.device_management.routes import device_management_bp
from api.general.routes import general_bp
from api.occupancy.routes import occupancy_bp
from api.profiles.routes import profiles_bp
from api.roles.routes import roles_bp
from api.room_management.routes import room_management_bp
from api.users.routes import users_bp


def register_blueprints(app):
    for blueprint in (
        general_bp,
        auth_bp,
        users_bp,
        profiles_bp,
        room_management_bp,
        device_management_bp,
        roles_bp,
        occupancy_bp,
        assistance_bp,
    ):
        app.register_blueprint(blueprint)
