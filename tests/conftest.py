import pytest

from api.authentication.routes import auth_bp
from api.occupancy.routes import occupancy_bp
from database import create_app
from database.extensions import db
from services.authentication.user import users_bp
from services.authentication.user_profile import profiles_bp
from services.role.role import roles_bp


@pytest.fixture
def app():
    app = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        }
    )
    assert app.config["SQLALCHEMY_DATABASE_URI"].startswith("sqlite:")

    app.register_blueprint(auth_bp)
    app.register_blueprint(roles_bp)
    app.register_blueprint(users_bp)
    app.register_blueprint(profiles_bp)
    app.register_blueprint(occupancy_bp)

    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()
