"""Create initial tables

Revision ID: 9eb97e9a8b09
Revises: bd571cb82bbd
Create Date: 2026-10-10 23:22:39.939200

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9eb97e9a8b09'
down_revision: Union[str, Sequence[str], None] = 'bd571cb82bbd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
