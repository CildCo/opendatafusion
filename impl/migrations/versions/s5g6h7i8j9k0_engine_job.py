"""engine jobs

Revision ID: s5g6h7i8j9k0
Revises: r4f5g6h7i8j9
Create Date: 2026-10-26 10:00:00
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "s5g6h7i8j9k0"
down_revision: Union[str, Sequence[str], None] = "r4f5g6h7i8j9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "engine_job",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer, "sqlite"),
                  primary_key=True, autoincrement=True),
        sa.Column("project_id", sa.Integer(),
                  sa.ForeignKey("project.id"), nullable=False),
        sa.Column("asset_id", sa.Integer(),
                  sa.ForeignKey("asset.id"), nullable=True),
        sa.Column("engine", sa.String(16), nullable=False),
        sa.Column("name", sa.String(63), nullable=False, unique=True),
        sa.Column("spec_json", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False,
                  server_default="pending"),
        sa.Column("external_id", sa.String(255), nullable=False,
                  server_default=""),
        sa.Column("submitted_by", sa.String(64), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False,
                  server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False,
                  server_default="2"),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("result_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("synced_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_engine_job_project_id", "engine_job", ["project_id"])
    op.create_index("ix_engine_job_asset_id", "engine_job", ["asset_id"])
    op.create_index("ix_engine_job_engine", "engine_job", ["engine"])
    op.create_index("ix_engine_job_status", "engine_job", ["status"])
    op.create_index("ix_engine_job_status_synced", "engine_job",
                    ["status", "synced_at"])


def downgrade() -> None:
    op.drop_table("engine_job")
