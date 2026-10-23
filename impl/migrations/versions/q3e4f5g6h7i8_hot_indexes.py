"""hot queue and delivery indexes

Revision ID: q3e4f5g6h7i8
Revises: o2d3e4f5g6h7
Create Date: 2026-10-21 15:20:00
"""
from typing import Sequence, Union

from alembic import op

revision: str = "q3e4f5g6h7i8"
down_revision: Union[str, Sequence[str], None] = "o2d3e4f5g6h7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index("ix_job_status_run_at", "job", ["status", "run_at"])
    op.create_index("ix_webhook_delivery_status_next", "webhook_delivery",
                    ["status", "next_attempt_at"])


def downgrade() -> None:
    op.drop_index("ix_webhook_delivery_status_next",
                  table_name="webhook_delivery")
    op.drop_index("ix_job_status_run_at", table_name="job")
