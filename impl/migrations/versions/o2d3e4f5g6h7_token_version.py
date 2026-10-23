"""user token version for session revocation

Revision ID: o2d3e4f5g6h7
Revises: n1c2d3e4f5g6
Create Date: 2026-10-21 11:30:00
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "o2d3e4f5g6h7"
down_revision: Union[str, Sequence[str], None] = "n1c2d3e4f5g6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("app_user") as batch:
        batch.add_column(sa.Column("token_version", sa.Integer(),
                                   nullable=False, server_default="0"))


def downgrade() -> None:
    with op.batch_alter_table("app_user") as batch:
        batch.drop_column("token_version")
