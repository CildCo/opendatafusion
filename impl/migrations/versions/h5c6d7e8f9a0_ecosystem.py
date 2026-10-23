"""ecosystem modules

Revision ID: h5c6d7e8f9a0
Revises: g4b5c6d7e8f9
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "h5c6d7e8f9a0"
down_revision: Union[str, Sequence[str], None] = "g4b5c6d7e8f9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "webhook_subscription",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("project.id"),
                  nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("url", sa.String(1024), nullable=False),
        sa.Column("secret_encrypted", sa.String(512), nullable=False),
        sa.Column("events_json", sa.JSON(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("created_by", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_status", sa.String(16), nullable=True),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True),
                  nullable=True),
        sa.Column("failure_count", sa.Integer(), nullable=False),
    )
    op.create_index("ix_webhook_subscription_project", "webhook_subscription",
                    ["project_id"])
    op.create_table(
        "webhook_delivery",
        sa.Column("id", sa.BigInteger().with_variant(
            sa.Integer(), "sqlite"), primary_key=True, autoincrement=True),
        sa.Column("subscription_id", sa.Integer(),
                  sa.ForeignKey("webhook_subscription.id"), nullable=False),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("project.id"),
                  nullable=False),
        sa.Column("event", sa.String(64), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True),
                  nullable=False),
        sa.Column("response_status", sa.Integer(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_webhook_delivery_subscription", "webhook_delivery",
                    ["subscription_id"])
    op.create_index("ix_webhook_delivery_project", "webhook_delivery",
                    ["project_id"])
    op.create_index("ix_webhook_delivery_status", "webhook_delivery",
                    ["status"])
    op.create_index("ix_webhook_delivery_next", "webhook_delivery",
                    ["next_attempt_at"])
    op.create_table(
        "file_object",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("project.id"),
                  nullable=False),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("content_type", sa.String(128), nullable=False),
        sa.Column("size", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("storage_key", sa.String(512), nullable=False),
        sa.Column("created_by", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_file_object_project", "file_object", ["project_id"])
    op.create_index("ix_file_object_sha", "file_object", ["sha256"])
    op.create_table(
        "portal_setting",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("project.id"),
                  nullable=False, unique=True),
        sa.Column("brand_name", sa.String(64), nullable=False),
        sa.Column("primary_color", sa.String(16), nullable=False),
        sa.Column("welcome_title", sa.String(128), nullable=False),
        sa.Column("welcome_text", sa.String(1000), nullable=False),
        sa.Column("hidden_menus", sa.JSON(), nullable=False),
        sa.Column("updated_by", sa.String(64), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_portal_setting_project", "portal_setting",
                    ["project_id"], unique=True)


def downgrade() -> None:
    op.drop_table("portal_setting")
    op.drop_table("file_object")
    op.drop_table("webhook_delivery")
    op.drop_table("webhook_subscription")
