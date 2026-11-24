"""scheduled dashboard reports

Revision ID: c6f7a8b9c0d1
Revises: b5e6f7a8b9c0
Create Date: 2026-11-24
"""
import sqlalchemy as sa
from alembic import op

revision = "c6f7a8b9c0d1"
down_revision = "b5e6f7a8b9c0"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "report_schedule",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(),
                  sa.ForeignKey("project.id"), nullable=False),
        sa.Column("asset_id", sa.Integer(), sa.ForeignKey("asset.id"),
                  nullable=False),
        sa.Column("cron", sa.String(length=64), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False,
                  server_default=sa.true()),
        sa.Column("created_by", sa.String(length=64), nullable=False),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_status", sa.String(length=16), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("last_file_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("asset_id"),
    )
    op.create_index("ix_report_schedule_project_id", "report_schedule",
                    ["project_id"])
    op.create_index("ix_report_schedule_asset_id", "report_schedule",
                    ["asset_id"])


def downgrade():
    op.drop_index("ix_report_schedule_asset_id", table_name="report_schedule")
    op.drop_index("ix_report_schedule_project_id",
                  table_name="report_schedule")
    op.drop_table("report_schedule")
