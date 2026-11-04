"""Create initial tables

Revision ID: 9eb97e9a8b09
Revises: bd571cb82bbd
Create Date: 2026-10-10 23:22:39.939200

"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "9eb97e9a8b09"
down_revision: str | Sequence[str] | None = "bd571cb82bbd"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""


def downgrade() -> None:
    """Downgrade schema."""
