"""share embed mode

Revision ID: i7d8e9f0a1b2
Revises: h6c7d8e9f0a1
Create Date: 2026-11-26
"""
import sqlalchemy as sa
from alembic import op

revision = "i7d8e9f0a1b2"
down_revision = "h6c7d8e9f0a1"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("share_link") as batch:
        batch.add_column(sa.Column("mode", sa.String(16), nullable=False,
                                   server_default="share"))


def downgrade():
    with op.batch_alter_table("share_link") as batch:
        batch.drop_column("mode")
