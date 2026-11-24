"""lakehouse maintenance schedules

Revision ID: e8b9c0d1e2f3
Revises: d7a8b9c0d1e2
Create Date: 2026-11-24
"""
import sqlalchemy as sa
from alembic import op

revision = "e8b9c0d1e2f3"
down_revision = "d7a8b9c0d1e2"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("job") as batch:
        batch.add_column(sa.Column(
            "project_id", sa.Integer(),
            sa.ForeignKey("project.id", name="fk_job_project_id"),
            nullable=True))
    op.create_index("ix_job_project_id", "job", ["project_id"])
    op.create_table(
        "lakehouse_maintenance",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(),
                  sa.ForeignKey("project.id"), nullable=False),
        sa.Column("datasource_id", sa.Integer(),
                  sa.ForeignKey("datasource.id"), nullable=False),
        sa.Column("schema_name", sa.String(length=128), nullable=False),
        sa.Column("table_name", sa.String(length=128), nullable=False,
                  server_default=""),
        sa.Column("cron", sa.String(length=64), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False,
                  server_default=sa.true()),
        sa.Column("optimize", sa.Boolean(), nullable=False,
                  server_default=sa.true()),
        sa.Column("expire_snapshots", sa.Boolean(), nullable=False,
                  server_default=sa.true()),
        sa.Column("retention", sa.String(length=16), nullable=False,
                  server_default="7d"),
        sa.Column("file_size_threshold", sa.String(length=16),
                  nullable=False, server_default="128MB"),
        sa.Column("created_by", sa.String(length=64), nullable=False),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_status", sa.String(length=16), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("project_id", "datasource_id", "schema_name",
                            "table_name"),
    )
    op.create_index("ix_lakehouse_maintenance_project_id",
                    "lakehouse_maintenance", ["project_id"])
    op.create_index("ix_lakehouse_maintenance_datasource_id",
                    "lakehouse_maintenance", ["datasource_id"])


def downgrade():
    op.drop_index("ix_lakehouse_maintenance_datasource_id",
                  table_name="lakehouse_maintenance")
    op.drop_index("ix_lakehouse_maintenance_project_id",
                  table_name="lakehouse_maintenance")
    op.drop_table("lakehouse_maintenance")
    op.drop_index("ix_job_project_id", table_name="job")
    with op.batch_alter_table("job") as batch:
        batch.drop_column("project_id")
