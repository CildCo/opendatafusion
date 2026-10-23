"""production hardening

Revision ID: i6d7e8f9a0b1
Revises: h5c6d7e8f9a0
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "i6d7e8f9a0b1"
down_revision: Union[str, Sequence[str], None] = "h5c6d7e8f9a0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("app_user", sa.Column("totp_secret_encrypted",
                                        sa.String(512), nullable=True))
    op.add_column("app_user", sa.Column("totp_enabled", sa.Boolean(),
                                        nullable=False,
                                        server_default=sa.false()))
    op.add_column("app_user", sa.Column("password_changed_at",
                                        sa.DateTime(timezone=True),
                                        nullable=True))
    op.add_column("ak_sk", sa.Column("ip_allowlist", sa.JSON(),
                                     nullable=True))
    op.add_column("ak_sk", sa.Column("rate_limit_per_min", sa.Integer(),
                                     nullable=True))
    op.create_table(
        "row_policy",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("project.id"),
                  nullable=False),
        sa.Column("dataset_id", sa.Integer(), sa.ForeignKey("asset.id"),
                  nullable=False),
        sa.Column("column", sa.String(128), nullable=False),
        sa.Column("op", sa.String(16), nullable=False),
        sa.Column("value", sa.JSON(), nullable=False),
        sa.Column("roles", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_row_policy_project", "row_policy", ["project_id"])
    op.create_index("ix_row_policy_dataset", "row_policy", ["dataset_id"])
    op.create_table(
        "api_rate",
        sa.Column("key", sa.String(200), primary_key=True),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False),
    )
    op.create_table(
        "api_call_stat",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("api_id", sa.Integer(), sa.ForeignKey("asset.id"),
                  nullable=False),
        sa.Column("ak", sa.String(64), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False),
        sa.Column("errors", sa.Integer(), nullable=False),
        sa.Column("total_ms", sa.Integer(), nullable=False),
        sa.UniqueConstraint("day", "api_id", "ak"),
    )
    op.create_index("ix_api_call_stat_day", "api_call_stat", ["day"])
    op.create_index("ix_api_call_stat_api", "api_call_stat", ["api_id"])
    op.create_index("ix_api_call_stat_ak", "api_call_stat", ["ak"])


def downgrade() -> None:
    op.drop_table("api_call_stat")
    op.drop_table("api_rate")
    op.drop_table("row_policy")
    op.drop_column("ak_sk", "rate_limit_per_min")
    op.drop_column("ak_sk", "ip_allowlist")
    op.drop_column("app_user", "password_changed_at")
    op.drop_column("app_user", "totp_enabled")
    op.drop_column("app_user", "totp_secret_encrypted")
