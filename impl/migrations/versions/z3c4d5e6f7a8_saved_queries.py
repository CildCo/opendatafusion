"""saved workbench queries

Revision ID: z3c4d5e6f7a8
Revises: y2b3c4d5e6f7
Create Date: 2026-11-23
"""
import sqlalchemy as sa
from alembic import op

revision = "z3c4d5e6f7a8"
down_revision = "y2b3c4d5e6f7"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "saved_query",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(),
                  sa.ForeignKey("project.id"), nullable=False),
        sa.Column("owner_id", sa.Integer(),
                  sa.ForeignKey("app_user.id"), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("tab", sa.String(length=16), nullable=False,
                  server_default="single"),
        sa.Column("datasource_id", sa.Integer(),
                  sa.ForeignKey("datasource.id"), nullable=True),
        sa.Column("sql_text", sa.Text(), nullable=False, server_default=""),
        sa.Column("sources_json", sa.JSON(), nullable=False,
                  server_default="[]"),
        sa.Column("row_limit", sa.Integer(), nullable=False,
                  server_default="1000"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
    )
    op.create_index("ix_saved_query_project_owner", "saved_query",
                    ["project_id", "owner_id"])


def downgrade():
    op.drop_index("ix_saved_query_project_owner", table_name="saved_query")
    op.drop_table("saved_query")
