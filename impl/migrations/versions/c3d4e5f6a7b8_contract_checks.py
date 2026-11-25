"""scheduled contract checks

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-11-25
"""
import sqlalchemy as sa
from alembic import op

revision = "c3d4e5f6a7b8"
down_revision = "b2c3d4e5f6a7"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "contract_check",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer, "sqlite"),
                  primary_key=True, autoincrement=True),
        sa.Column("project_id", sa.Integer(),
                  sa.ForeignKey("project.id"), nullable=False),
        sa.Column("asset_id", sa.Integer(),
                  sa.ForeignKey("asset.id"), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False,
                  server_default="ok"),
        sa.Column("issues_json", sa.JSON(), nullable=False,
                  server_default="[]"),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_contract_check_project_id", "contract_check",
                    ["project_id"])
    op.create_index("ix_contract_check_asset_id", "contract_check",
                    ["asset_id"])
    op.create_index("ix_contract_check_checked_at", "contract_check",
                    ["checked_at"])
    op.create_index("ix_contract_check_asset_checked", "contract_check",
                    ["asset_id", "checked_at"])


def downgrade():
    op.drop_index("ix_contract_check_asset_checked",
                  table_name="contract_check")
    op.drop_index("ix_contract_check_checked_at", table_name="contract_check")
    op.drop_index("ix_contract_check_asset_id", table_name="contract_check")
    op.drop_index("ix_contract_check_project_id", table_name="contract_check")
    op.drop_table("contract_check")
