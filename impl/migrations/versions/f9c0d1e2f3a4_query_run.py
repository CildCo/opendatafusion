"""query run history

Revision ID: f9c0d1e2f3a4
Revises: e8b9c0d1e2f3
Create Date: 2026-11-24
"""
import sqlalchemy as sa
from alembic import op

revision = "f9c0d1e2f3a4"
down_revision = "e8b9c0d1e2f3"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "query_run",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer,
                                                     "sqlite"),
                  primary_key=True, autoincrement=True),
        sa.Column("project_id", sa.Integer(),
                  sa.ForeignKey("project.id"), nullable=False),
        sa.Column("datasource_id", sa.Integer(),
                  sa.ForeignKey("datasource.id"), nullable=True),
        sa.Column("actor", sa.String(length=64), nullable=False,
                  server_default=""),
        sa.Column("source", sa.String(length=16), nullable=False,
                  server_default="workbench"),
        sa.Column("status", sa.String(length=8), nullable=False,
                  server_default="ok"),
        sa.Column("sql_hash", sa.String(length=64), nullable=False,
                  server_default=""),
        sa.Column("sql_preview", sa.Text(), nullable=False,
                  server_default=""),
        sa.Column("sql_text", sa.Text(), nullable=False,
                  server_default=""),
        sa.Column("rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_query_run_project_id", "query_run", ["project_id"])
    op.create_index("ix_query_run_datasource_id", "query_run",
                    ["datasource_id"])
    op.create_index("ix_query_run_created_at", "query_run", ["created_at"])
    op.create_index("ix_query_run_project_created", "query_run",
                    ["project_id", "created_at"])
    op.create_index("ix_query_run_datasource_created", "query_run",
                    ["datasource_id", "created_at"])


def downgrade():
    op.drop_index("ix_query_run_datasource_created", table_name="query_run")
    op.drop_index("ix_query_run_project_created", table_name="query_run")
    op.drop_index("ix_query_run_created_at", table_name="query_run")
    op.drop_index("ix_query_run_datasource_id", table_name="query_run")
    op.drop_index("ix_query_run_project_id", table_name="query_run")
    op.drop_table("query_run")
