"""add user created at

Revision ID: f10820aa102b
Revises: f5cdee790192
Create Date: 2026-09-15 14:00:31.969394

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f10820aa102b'
down_revision: Union[str, Sequence[str], None] = 'f5cdee790192'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # The initial revision already creates google_sub as a unique constraint.
    # This revision was generated against a schema that does not exist here.
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
