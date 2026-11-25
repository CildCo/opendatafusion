"""general asset grants and requests

Revision ID: e5f6a7b8c9d0
Revises: c3d4e5f6a7b8
Create Date: 2026-11-25
"""
import sqlalchemy as sa
from alembic import op

revision = "e5f6a7b8c9d0"
down_revision = "c3d4e5f6a7b8"
branch_labels = None
depends_on = None


def upgrade():
    op.rename_table("interface_grant", "asset_grant")
    op.rename_table("interface_request", "asset_request")
    for table in ("asset_grant", "asset_request"):
        with op.batch_alter_table(table) as batch:
            batch.alter_column("interface_asset_id", new_column_name="asset_id")
            batch.add_column(sa.Column(
                "asset_type", sa.String(length=16), nullable=False,
                server_default="api"))


def downgrade():
    for table in ("asset_grant", "asset_request"):
        with op.batch_alter_table(table) as batch:
            batch.drop_column("asset_type")
            batch.alter_column("asset_id", new_column_name="interface_asset_id")
    op.rename_table("asset_request", "interface_request")
    op.rename_table("asset_grant", "interface_grant")
