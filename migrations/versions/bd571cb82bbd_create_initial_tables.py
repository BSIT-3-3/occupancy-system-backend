"""Create initial tables

Revision ID: bd571cb82bbd
Revises: 5cbd76f58c6b
Create Date: 2026-10-10 23:17:56.685445

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'bd571cb82bbd'
down_revision: Union[str, Sequence[str], None] = '5cbd76f58c6b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
