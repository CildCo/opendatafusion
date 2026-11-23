"""platform foundation: notifications, cancellations and legacy migration

Revision ID: y2b3c4d5e6f7
Revises: x1a2b3c4d5e6
Create Date: 2026-11-23
"""
import sqlalchemy as sa
from alembic import op

revision = "y2b3c4d5e6f7"
down_revision = "x1a2b3c4d5e6"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("flow", sa.Column("migrated_asset_id", sa.Integer(),
                                    nullable=True))
    op.add_column("data_interface", sa.Column("migrated_asset_id",
                                              sa.Integer(), nullable=True))
    op.add_column("job", sa.Column("cancel_requested", sa.Boolean(),
                                   nullable=False,
                                   server_default=sa.false()))
    op.create_table(
        "notification",
        sa.Column("id", sa.BigInteger(), primary_key=True,
                  autoincrement=True),
        sa.Column("project_id", sa.Integer(),
                  sa.ForeignKey("project.id"), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False,
                  server_default="info"),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("body", sa.Text(), nullable=False, server_default=""),
        sa.Column("link", sa.String(length=256), nullable=False,
                  server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_notification_project_created", "notification",
                    ["project_id", "created_at"])
    op.create_table(
        "notification_read",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("app_user.id"),
                  nullable=False),
        sa.Column("notification_id", sa.BigInteger(),
                  sa.ForeignKey("notification.id"), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "notification_id",
                            name="uq_notification_read_user"),
    )
    op.create_index("ix_notification_read_user", "notification_read",
                    ["user_id"])


def downgrade():
    op.drop_index("ix_notification_read_user", table_name="notification_read")
    op.drop_table("notification_read")
    op.drop_index("ix_notification_project_created", table_name="notification")
    op.drop_table("notification")
    op.drop_column("job", "cancel_requested")
    op.drop_column("data_interface", "migrated_asset_id")
    op.drop_column("flow", "migrated_asset_id")
