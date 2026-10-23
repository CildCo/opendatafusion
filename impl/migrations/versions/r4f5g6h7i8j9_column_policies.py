"""column sensitivity policies

Revision ID: r4f5g6h7i8j9
Revises: q3e4f5g6h7i8
Create Date: 2026-10-21 15:40:00
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "r4f5g6h7i8j9"
down_revision: Union[str, Sequence[str], None] = "q3e4f5g6h7i8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "column_policy",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(),
                  sa.ForeignKey("project.id"), nullable=False),
        sa.Column("datasource_id", sa.Integer(),
                  sa.ForeignKey("datasource.id"), nullable=False),
        sa.Column("schema_name", sa.String(128), nullable=False,
                  server_default=""),
        sa.Column("table_name", sa.String(128), nullable=False),
        sa.Column("column_name", sa.String(128), nullable=False),
        sa.Column("classification", sa.String(32), nullable=False,
                  server_default="pii"),
        sa.Column("mask_type", sa.String(32), nullable=False,
                  server_default="redact"),
        sa.Column("exempt_roles_json", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("datasource_id", "schema_name", "table_name",
                            "column_name"),
    )
    op.create_index("ix_column_policy_project_id", "column_policy",
                    ["project_id"])
    op.create_index("ix_column_policy_datasource_id", "column_policy",
                    ["datasource_id"])


def downgrade() -> None:
    op.drop_table("column_policy")
