from sqlalchemy.exc import SQLAlchemyError
from werkzeug.security import check_password_hash

from database.extensions import db
from database.models.user import User
from services.errors import InactiveAccountError, InvalidCredentialsError


def authenticate_user(username, password):
    try:
        user = db.session.query(User).filter_by(username=username).first()
    except SQLAlchemyError:
        db.session.rollback()
        raise

    if user is None or not check_password_hash(user.password, password):
        raise InvalidCredentialsError("Invalid username or password")
    if (user.status or "").upper() != "ACTIVE":
        raise InactiveAccountError("Account is inactive")
    if user.role is None or user.role.role_name != "ADMIN":
        raise InvalidCredentialsError("Invalid username or password")
    return user
