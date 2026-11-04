"""Keep ADMIN and USER roles and remove other roles after reference checks.

Revision ID: b7d3e1a9c642
Revises: a8c19e2d6f30
Create Date: 2026-11-04 00:00:00.000000

The migration deliberately stops if any user still references a role other than
ADMIN or USER. Those accounts must be reviewed before this revision can apply.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b7d3e1a9c642"
down_revision: str | Sequence[str] | None = "a8c19e2d6f30"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    connection = op.get_bind()
    role = sa.table(
        "role",
        sa.column("role_id", sa.Integer),
        sa.column("role_name", sa.String),
        sa.column("description", sa.String),
    )
    user = sa.table(
        "users",
        sa.column("user_id", sa.Integer),
        sa.column("role_id", sa.Integer),
    )

    for role_name, description in (
        ("ADMIN", "System administrator"),
        ("USER", "Registered user"),
    ):
        matching_ids = connection.execute(
            sa.select(role.c.role_id).where(
                sa.func.lower(role.c.role_name) == role_name.lower()
            )
        ).scalars().all()
        if len(matching_ids) > 1:
            raise RuntimeError(
                f"Multiple {role_name} role rows exist; reconcile them before migration"
            )
        if matching_ids:
            connection.execute(
                sa.update(role)
                .where(role.c.role_id == matching_ids[0])
                .values(role_name=role_name)
            )
        else:
            connection.execute(
                sa.insert(role)
                .values(role_name=role_name, description=description)
            )
    removable_roles = sa.func.upper(role.c.role_name).not_in(["ADMIN", "USER"])
    non_retained_user_count = connection.execute(
        sa.select(sa.func.count())
        .select_from(user.join(role, user.c.role_id == role.c.role_id))
        .where(removable_roles)
    ).scalar_one()
    if non_retained_user_count:
        raise RuntimeError(
            f"{non_retained_user_count} user account(s) reference unsupported roles; "
            "review those accounts before applying this migration"
        )

    connection.execute(sa.delete(role).where(removable_roles))


def downgrade() -> None:
    # Removed role rows cannot be restored without knowing their original metadata.
    raise RuntimeError(
        "This role cleanup cannot be reversed automatically; restore role data manually"
    )
