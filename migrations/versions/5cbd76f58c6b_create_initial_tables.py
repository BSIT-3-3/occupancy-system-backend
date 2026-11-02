"""Create initial tables

Revision ID: 5cbd76f58c6b
Revises:
Create Date: 2026-10-10 23:09:46.395155

"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "5cbd76f58c6b"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""


def downgrade() -> None:
    """Downgrade schema."""
