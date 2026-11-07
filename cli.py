import click
from flask import current_app
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from werkzeug.security import generate_password_hash

from database.extensions import db
from database.models.role import Role
from database.models.user import User
from services.device.monitoring import reconcile_offline_devices
from services.errors import ServiceError
from services.security.device_keys import provision_device_key


def register_cli_commands(app):
    @app.cli.command("create-admin")
    @click.option("--username", prompt=True)
    @click.password_option(prompt=True, confirmation_prompt=True)
    def create_admin(username, password):
        """Create an admin account from an operator-controlled shell."""
        username = username.strip()
        if not username:
            raise click.ClickException("Username is required.")
        if len(password) < 8:
            raise click.ClickException("Admin passwords must be at least 8 characters.")

        try:
            if User.query.filter_by(username=username).first() is not None:
                raise click.ClickException("An account with that username already exists.")

            role = Role.query.filter_by(role_name="ADMIN").first()
            if role is None:
                role = Role(role_name="ADMIN", description="System administrator")
                db.session.add(role)
                db.session.flush()

            db.session.add(
                User(
                    username=username,
                    password=generate_password_hash(password),
                    full_name=username,
                    role_id=role.role_id,
                    status="ACTIVE",
                )
            )
            db.session.commit()
        except click.ClickException:
            db.session.rollback()
            raise
        except IntegrityError:
            db.session.rollback()
            raise click.ClickException("An account with that username already exists.")
        except SQLAlchemyError:
            db.session.rollback()
            current_app.logger.exception("Admin bootstrap failed")
            raise click.ClickException(
                "Admin account creation failed. Check application logs."
            ) from None
        click.echo("Admin account created.")

    @app.cli.command("rotate-device-key")
    @click.option("--device-id", prompt=True)
    @click.option(
        "--activate",
        is_flag=True,
        help="Activate a pending device while provisioning its key.",
    )
    def rotate_device_key(device_id, activate):
        """Provision or rotate a device's API key; the key is shown once."""
        try:
            credential = provision_device_key(device_id.strip(), activate=activate)
        except ServiceError as error:
            raise click.ClickException(str(error)) from None
        except SQLAlchemyError as error:
            db.session.rollback()
            current_app.logger.error(
                "Device key provisioning failed (%s)", type(error).__name__
            )
            raise click.ClickException("Device key provisioning failed.") from None

        click.echo(f"Device key (shown once): {credential}")

    @app.cli.command("reconcile-device-status")
    def reconcile_device_status():
        """Mark registered devices offline after their heartbeat timeout."""
        try:
            changed = reconcile_offline_devices(
                current_app.config["DEVICE_HEARTBEAT_TIMEOUT_SECONDS"]
            )
        except SQLAlchemyError as error:
            db.session.rollback()
            current_app.logger.error(
                "Device status reconciliation failed (%s)", type(error).__name__
            )
            raise click.ClickException(
                "Device status reconciliation failed. Check application logs."
            ) from None

        click.echo(f"Marked {changed} device(s) offline.")
