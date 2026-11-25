"""datasource rate and concurrency limits

Revision ID: b2c3d4e5f6a7
Revises: f9c0d1e2f3a4
Create Date: 2026-11-25
"""
import sqlalchemy as sa
from alembic import op

revision = "b2c3d4e5f6a7"
down_revision = "f9c0d1e2f3a4"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("datasource") as batch:
        batch.add_column(sa.Column("limit_json", sa.JSON(), nullable=True))


def downgrade():
    with op.batch_alter_table("datasource") as batch:
        batch.drop_column("limit_json")
