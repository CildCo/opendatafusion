"""grant uniqueness

Revision ID: g4b5c6d7e8f9
Revises: f3a4b5c6d7e8
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "g4b5c6d7e8f9"
down_revision: Union[str, Sequence[str], None] = "f3a4b5c6d7e8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ux_interface_grant_active", "interface_grant",
        ["interface_asset_id", "grantee_project_id"], unique=True,
        postgresql_where=sa.text("revoked_at IS NULL"),
        sqlite_where=sa.text("revoked_at IS NULL"))
    op.create_index(
        "ux_interface_request_pending", "interface_request",
        ["interface_asset_id", "grantee_project_id"], unique=True,
        postgresql_where=sa.text("status = 'pending'"),
        sqlite_where=sa.text("status = 'pending'"))


def downgrade() -> None:
    op.drop_index("ux_interface_request_pending",
                  table_name="interface_request")
    op.drop_index("ux_interface_grant_active", table_name="interface_grant")
