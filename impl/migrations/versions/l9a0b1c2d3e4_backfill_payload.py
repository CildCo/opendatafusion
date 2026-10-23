"""backfill job payload

Revision ID: l9a0b1c2d3e4
Revises: k8f9a0b1c2d3
Create Date: 2026-10-21 10:40:00
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "l9a0b1c2d3e4"
down_revision: Union[str, Sequence[str], None] = "k8f9a0b1c2d3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("job") as batch:
        batch.add_column(sa.Column("payload_json", sa.JSON(),
                                   nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("job") as batch:
        batch.drop_column("payload_json")
