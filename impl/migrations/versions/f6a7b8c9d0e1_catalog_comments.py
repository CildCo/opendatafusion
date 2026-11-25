"""catalog comments

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-11-25
"""
import sqlalchemy as sa
from alembic import op

revision = "f6a7b8c9d0e1"
down_revision = "e5f6a7b8c9d0"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "catalog_comment",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(),
                  sa.ForeignKey("project.id"), nullable=False),
        sa.Column("dataset_id", sa.Integer(),
                  sa.ForeignKey("dataset.id"), nullable=False),
        sa.Column("actor", sa.String(length=64), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False,
                  server_default="open"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_by", sa.String(length=64), nullable=True),
    )
    op.create_index("ix_catalog_comment_project_id", "catalog_comment",
                    ["project_id"])
    op.create_index("ix_catalog_comment_dataset_id", "catalog_comment",
                    ["dataset_id"])
    op.create_index("ix_catalog_comment_created_at", "catalog_comment",
                    ["created_at"])
    op.create_index("ix_catalog_comment_dataset_created", "catalog_comment",
                    ["dataset_id", "created_at"])


def downgrade():
    op.drop_table("catalog_comment")
