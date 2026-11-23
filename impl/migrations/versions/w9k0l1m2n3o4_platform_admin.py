"""platform administration

Revision ID: w9k0l1m2n3o4
Revises: v8j9k0l1m2n3
"""
from alembic import op
import sqlalchemy as sa

revision = "w9k0l1m2n3o4"
down_revision = "v8j9k0l1m2n3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "app_user",
        sa.Column("platform_admin", sa.Boolean(), nullable=False,
                  server_default=sa.false()))
    op.execute("UPDATE app_user SET platform_admin = TRUE "
               "WHERE role = 'admin'")
    op.add_column("project", sa.Column("quota_json", sa.JSON(), nullable=True))
    op.create_table(
        "platform_setting",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("settings_json", sa.JSON(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("platform_setting")
    op.drop_column("project", "quota_json")
    op.drop_column("app_user", "platform_admin")
