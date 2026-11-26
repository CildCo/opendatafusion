"""asset run policy

Revision ID: c9d0e1f2a3b4
Revises: b8c9d0e1f2a3
Create Date: 2026-11-26
"""
import sqlalchemy as sa
from alembic import op

revision = "c9d0e1f2a3b4"
down_revision = "b8c9d0e1f2a3"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("asset") as batch:
        batch.add_column(sa.Column("max_attempts", sa.Integer(),
                                   nullable=False, server_default="3"))
        batch.add_column(sa.Column("retry_backoff_seconds", sa.Integer(),
                                   nullable=False, server_default="30"))


def downgrade():
    with op.batch_alter_table("asset") as batch:
        batch.drop_column("retry_backoff_seconds")
        batch.drop_column("max_attempts")
