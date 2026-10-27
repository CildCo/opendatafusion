"""cdc sources

Revision ID: t6h7i8j9k0l1
Revises: s5g6h7i8j9k0
Create Date: 2026-10-26 12:00:00
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "t6h7i8j9k0l1"
down_revision: Union[str, Sequence[str], None] = "s5g6h7i8j9k0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "cdc_source",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(),
                  sa.ForeignKey("project.id"), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("connector_name", sa.String(128), nullable=False,
                  unique=True),
        sa.Column("status", sa.String(16), nullable=False,
                  server_default="pending"),
        sa.Column("config_json", sa.JSON(), nullable=False),
        sa.Column("password_encrypted", sa.String(512), nullable=False,
                  server_default=""),
        sa.Column("created_by", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("project_id", "name"),
    )
    op.create_index("ix_cdc_source_project_id", "cdc_source", ["project_id"])


def downgrade() -> None:
    op.drop_table("cdc_source")
