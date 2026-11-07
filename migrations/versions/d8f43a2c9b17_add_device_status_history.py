"""Add device connectivity state and transition history.

Revision ID: d8f43a2c9b17
Revises: c1a9e8d4f672
Create Date: 2026-11-08 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d8f43a2c9b17"
down_revision: str | Sequence[str] | None = "c1a9e8d4f672"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "room_device",
        sa.Column(
            "current_status",
            sa.String(length=10),
            server_default=sa.text("'UNKNOWN'"),
            nullable=False,
        ),
    )
    op.add_column(
        "room_device",
        sa.Column("last_communication_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_check_constraint(
        "ck_room_device_current_status",
        "room_device",
        "current_status IN ('UNKNOWN', 'ONLINE', 'OFFLINE')",
    )

    op.create_table(
        "device_status_log",
        sa.Column("device_status_id", sa.Integer(), nullable=False),
        sa.Column("device_id", sa.String(length=20), nullable=False),
        sa.Column("previous_status", sa.String(length=10), nullable=False),
        sa.Column("new_status", sa.String(length=10), nullable=False),
        sa.Column(
            "changed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("reason", sa.String(length=50), nullable=False),
        sa.CheckConstraint(
            "previous_status IN ('UNKNOWN', 'ONLINE', 'OFFLINE')",
            name="ck_device_status_log_previous_status",
        ),
        sa.CheckConstraint(
            "new_status IN ('UNKNOWN', 'ONLINE', 'OFFLINE')",
            name="ck_device_status_log_new_status",
        ),
        sa.CheckConstraint(
            "previous_status <> new_status",
            name="ck_device_status_log_status_changed",
        ),
        sa.ForeignKeyConstraint(["device_id"], ["room_device.device_id"]),
        sa.PrimaryKeyConstraint("device_status_id"),
    )
    op.create_index(
        "ix_device_status_log_device_changed_at",
        "device_status_log",
        ["device_id", "changed_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_device_status_log_device_changed_at", table_name="device_status_log"
    )
    op.drop_table("device_status_log")
    op.drop_constraint(
        "ck_room_device_current_status", "room_device", type_="check"
    )
    op.drop_column("room_device", "last_communication_at")
    op.drop_column("room_device", "current_status")
