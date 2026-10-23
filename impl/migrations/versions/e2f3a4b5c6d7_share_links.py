"""share links

Revision ID: e2f3a4b5c6d7
Revises: d4e5f6a7b8c9
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e2f3a4b5c6d7"
down_revision: Union[str, Sequence[str], None] = "d4e5f6a7b8c9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "share_link",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("project.id"),
                  nullable=False),
        sa.Column("asset_id", sa.Integer(), sa.ForeignKey("asset.id"),
                  nullable=False),
        sa.Column("asset_type", sa.String(32), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("created_by", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_share_link_project_id", "share_link", ["project_id"])
    op.create_index("ix_share_link_asset_id", "share_link", ["asset_id"])
    op.create_index("ix_share_link_token_hash", "share_link", ["token_hash"],
                    unique=True)


def downgrade() -> None:
    op.drop_table("share_link")
