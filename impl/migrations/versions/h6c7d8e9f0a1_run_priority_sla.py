"""run priority and duration SLA

Revision ID: h6c7d8e9f0a1
Revises: d1e2f3a4b5c6
Create Date: 2026-11-26
"""
import sqlalchemy as sa
from alembic import op

revision = "h6c7d8e9f0a1"
down_revision = "d1e2f3a4b5c6"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("asset") as batch:
        batch.add_column(sa.Column("priority", sa.Integer(),
                                   nullable=False, server_default="0"))
        batch.add_column(sa.Column("max_duration_seconds", sa.Integer(),
                                   nullable=True))
        batch.create_index("ix_asset_priority", ["priority"])
    with op.batch_alter_table("job") as batch:
        batch.add_column(sa.Column("priority", sa.Integer(),
                                   nullable=False, server_default="0"))
        batch.create_index("ix_job_queue", ["status", "priority", "run_at"])


def downgrade():
    with op.batch_alter_table("job") as batch:
        batch.drop_index("ix_job_queue")
        batch.drop_column("priority")
    with op.batch_alter_table("asset") as batch:
        batch.drop_index("ix_asset_priority")
        batch.drop_column("max_duration_seconds")
        batch.drop_column("priority")
