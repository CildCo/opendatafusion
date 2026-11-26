"""catalog external metadata fields

Revision ID: j8e9f0a1b2c3
Revises: i7d8e9f0a1b2
Create Date: 2026-11-26
"""
import sqlalchemy as sa
from alembic import op

revision = "j8e9f0a1b2c3"
down_revision = "i7d8e9f0a1b2"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("dataset") as batch:
        batch.add_column(sa.Column("description", sa.Text(),
                                   nullable=False, server_default=""))
        batch.add_column(sa.Column("owner", sa.String(64),
                                   nullable=False, server_default=""))
    with op.batch_alter_table("dataset_column") as batch:
        batch.add_column(sa.Column("description", sa.Text(),
                                   nullable=False, server_default=""))


def downgrade():
    with op.batch_alter_table("dataset_column") as batch:
        batch.drop_column("description")
    with op.batch_alter_table("dataset") as batch:
        batch.drop_column("owner")
        batch.drop_column("description")
