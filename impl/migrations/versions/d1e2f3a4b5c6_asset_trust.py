"""asset trust and lifecycle

Revision ID: d1e2f3a4b5c6
Revises: c9d0e1f2a3b4
Create Date: 2026-11-26
"""
import sqlalchemy as sa
from alembic import op

revision = "d1e2f3a4b5c6"
down_revision = "c9d0e1f2a3b4"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("asset") as batch:
        batch.add_column(sa.Column("certification", sa.String(16),
                                   nullable=False, server_default="none"))
        batch.add_column(sa.Column("certified_by", sa.String(64),
                                   nullable=True))
        batch.add_column(sa.Column("certified_at",
                                   sa.DateTime(timezone=True),
                                   nullable=True))
        batch.add_column(sa.Column("lifecycle", sa.String(16),
                                   nullable=False, server_default="active"))
        batch.add_column(sa.Column("lifecycle_note", sa.Text(),
                                   nullable=False, server_default=""))
        batch.add_column(sa.Column("lifecycle_changed_at",
                                   sa.DateTime(timezone=True),
                                   nullable=True))
        batch.create_index("ix_asset_certification", ["certification"])
        batch.create_index("ix_asset_lifecycle", ["lifecycle"])


def downgrade():
    with op.batch_alter_table("asset") as batch:
        batch.drop_index("ix_asset_lifecycle")
        batch.drop_index("ix_asset_certification")
        batch.drop_column("lifecycle_changed_at")
        batch.drop_column("lifecycle_note")
        batch.drop_column("lifecycle")
        batch.drop_column("certified_at")
        batch.drop_column("certified_by")
        batch.drop_column("certification")
