"""governance, health and operations metadata

Revision ID: x1a2b3c4d5e6
Revises: w9k0l1m2n3o4
Create Date: 2026-11-23
"""
import sqlalchemy as sa
from alembic import op

revision = "x1a2b3c4d5e6"
down_revision = "w9k0l1m2n3o4"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("datasource", sa.Column("auto_sync_minutes", sa.Integer(),
                                          nullable=False, server_default="0"))
    op.add_column("datasource", sa.Column("last_sync_at",
                                          sa.DateTime(timezone=True),
                                          nullable=True))
    op.add_column("datasource", sa.Column("last_sync_status",
                                          sa.String(length=16),
                                          nullable=True))
    op.create_table(
        "datasource_health",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("datasource_id", sa.Integer(),
                  sa.ForeignKey("datasource.id"), nullable=False, index=True),
        sa.Column("action", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=False,
                  server_default="0"),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now(), index=True),
    )
    op.add_column("quality_rule", sa.Column("schedule_cron",
                                            sa.String(length=64),
                                            nullable=True))
    op.add_column("quality_rule", sa.Column("last_run_at",
                                            sa.DateTime(timezone=True),
                                            nullable=True))
    op.add_column("quality_rule", sa.Column("alert_on_fail", sa.Boolean(),
                                            nullable=False,
                                            server_default=sa.false()))
    op.add_column("column_policy", sa.Column("source", sa.String(length=16),
                                             nullable=False,
                                             server_default="manual"))


def downgrade():
    op.drop_column("column_policy", "source")
    op.drop_column("quality_rule", "alert_on_fail")
    op.drop_column("quality_rule", "last_run_at")
    op.drop_column("quality_rule", "schedule_cron")
    op.drop_table("datasource_health")
    op.drop_column("datasource", "last_sync_status")
    op.drop_column("datasource", "last_sync_at")
    op.drop_column("datasource", "auto_sync_minutes")
