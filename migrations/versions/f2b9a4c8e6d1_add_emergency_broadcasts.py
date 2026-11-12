"""Add emergency broadcasts and their target rooms.

Revision ID: f2b9a4c8e6d1
Revises: d8f43a2c9b17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f2b9a4c8e6d1"
down_revision: str | Sequence[str] | None = "d8f43a2c9b17"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "emergency_broadcast",
        sa.Column("broadcast_id", sa.Integer(), nullable=False),
        sa.Column("message_text", sa.String(length=500), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("broadcast_id"),
    )
    op.create_table(
        "emergency_broadcast_target",
        sa.Column("target_id", sa.Integer(), nullable=False),
        sa.Column("broadcast_id", sa.Integer(), nullable=False),
        sa.Column("room_id", sa.Integer(), nullable=False),
        sa.Column(
            "delivery_status",
            sa.String(length=20),
            server_default=sa.text("'PENDING'"),
            nullable=False,
        ),
        sa.Column("dispatched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failure_reason", sa.String(length=250), nullable=True),
        sa.CheckConstraint(
            "delivery_status IN ('PENDING', 'DISPATCHED', 'ACKNOWLEDGED', 'FAILED')",
            name="ck_broadcast_target_status",
        ),
        sa.ForeignKeyConstraint(["broadcast_id"], ["emergency_broadcast.broadcast_id"]),
        sa.ForeignKeyConstraint(["room_id"], ["room.room_id"]),
        sa.PrimaryKeyConstraint("target_id"),
        sa.UniqueConstraint("broadcast_id", "room_id", name="uq_broadcast_target_room"),
    )
    op.create_index(
        "ix_emergency_broadcast_target_broadcast_id",
        "emergency_broadcast_target",
        ["broadcast_id"],
    )
    op.create_index(
        "ix_emergency_broadcast_target_room_id",
        "emergency_broadcast_target",
        ["room_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_emergency_broadcast_target_room_id", table_name="emergency_broadcast_target"
    )
    op.drop_index(
        "ix_emergency_broadcast_target_broadcast_id",
        table_name="emergency_broadcast_target",
    )
    op.drop_table("emergency_broadcast_target")
    op.drop_table("emergency_broadcast")
