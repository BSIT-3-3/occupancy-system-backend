"""Add per-device credential hashes.

Revision ID: a8c19e2d6f30
Revises: 4eeb229fbbb7
Create Date: 2026-11-04 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a8c19e2d6f30"
down_revision: str | Sequence[str] | None = "4eeb229fbbb7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "room_device",
        sa.Column("credential_hash", sa.String(length=64), nullable=True),
    )
    op.create_unique_constraint(
        "uq_room_device_credential_hash", "room_device", ["credential_hash"]
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_room_device_credential_hash", "room_device", type_="unique"
    )
    op.drop_column("room_device", "credential_hash")
