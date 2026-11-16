from api.assistance.routes import assistance_bp
from api.authentication.routes import auth_bp
from api.device_management.routes import device_management_bp
from api.device_monitoring.routes import device_monitoring_bp
from api.emergency_notification.routes import (
    emergency_broadcast_bp,
    emergency_broadcast_gateway_bp,
)
from api.general.routes import general_bp
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
        device_monitoring_bp,
        emergency_broadcast_bp,
        emergency_broadcast_gateway_bp,
        roles_bp,
    ):
        app.register_blueprint(blueprint)
