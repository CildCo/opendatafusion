"""menu permissions

Revision ID: j7e8f9a0b1c2
Revises: i6d7e8f9a0b1
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "j7e8f9a0b1c2"
down_revision: Union[str, Sequence[str], None] = "i6d7e8f9a0b1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("portal_setting",
                  sa.Column("allowed_menus", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("portal_setting", "allowed_menus")
