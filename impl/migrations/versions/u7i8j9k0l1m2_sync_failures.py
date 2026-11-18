"""engine job sync failures

Revision ID: u7i8j9k0l1m2
Revises: t6h7i8j9k0l1
Create Date: 2026-11-17 16:00:00
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "u7i8j9k0l1m2"
down_revision: Union[str, Sequence[str], None] = "t6h7i8j9k0l1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("engine_job", sa.Column(
        "sync_failures", sa.Integer(), nullable=False, server_default="0"))


def downgrade() -> None:
    op.drop_column("engine_job", "sync_failures")
