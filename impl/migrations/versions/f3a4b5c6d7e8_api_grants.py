"""api grants

Revision ID: f3a4b5c6d7e8
Revises: e2f3a4b5c6d7
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f3a4b5c6d7e8"
down_revision: Union[str, Sequence[str], None] = "e2f3a4b5c6d7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "interface_grant",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("interface_asset_id", sa.Integer(),
                  sa.ForeignKey("asset.id"), nullable=False),
        sa.Column("owner_project_id", sa.Integer(),
                  sa.ForeignKey("project.id"), nullable=False),
        sa.Column("grantee_project_id", sa.Integer(),
                  sa.ForeignKey("project.id"), nullable=False),
        sa.Column("granted_by", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_interface_grant_asset", "interface_grant",
                    ["interface_asset_id"])
    op.create_index("ix_interface_grant_owner", "interface_grant",
                    ["owner_project_id"])
    op.create_index("ix_interface_grant_grantee", "interface_grant",
                    ["grantee_project_id"])
    op.create_table(
        "interface_request",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("interface_asset_id", sa.Integer(),
                  sa.ForeignKey("asset.id"), nullable=False),
        sa.Column("owner_project_id", sa.Integer(),
                  sa.ForeignKey("project.id"), nullable=False),
        sa.Column("grantee_project_id", sa.Integer(),
                  sa.ForeignKey("project.id"), nullable=False),
        sa.Column("requested_by", sa.String(64), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decided_by", sa.String(64), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_interface_request_asset", "interface_request",
                    ["interface_asset_id"])
    op.create_index("ix_interface_request_owner", "interface_request",
                    ["owner_project_id"])
    op.create_index("ix_interface_request_grantee", "interface_request",
                    ["grantee_project_id"])


def downgrade() -> None:
    op.drop_table("interface_request")
    op.drop_table("interface_grant")
