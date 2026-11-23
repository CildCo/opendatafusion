"""environment bundles

Revision ID: b5e6f7a8b9c0
Revises: a4d5e6f7a8b9
Create Date: 2026-11-24
"""
import sqlalchemy as sa
from alembic import op

revision = "b5e6f7a8b9c0"
down_revision = "a4d5e6f7a8b9"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("project", sa.Column("environment", sa.String(length=16),
                                       nullable=False,
                                       server_default="dev"))


def downgrade():
    op.drop_column("project", "environment")
