"""column lineage columns

Revision ID: m0b1c2d3e4f5
Revises: l9a0b1c2d3e4
Create Date: 2026-10-21 10:55:00
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "m0b1c2d3e4f5"
down_revision: Union[str, Sequence[str], None] = "l9a0b1c2d3e4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("lineage_edge") as batch:
        batch.add_column(sa.Column("from_column", sa.String(256),
                                   nullable=True))
        batch.add_column(sa.Column("to_column", sa.String(256),
                                   nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("lineage_edge") as batch:
        batch.drop_column("to_column")
        batch.drop_column("from_column")
