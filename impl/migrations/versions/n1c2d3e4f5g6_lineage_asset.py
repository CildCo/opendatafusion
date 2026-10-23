"""link lineage edges to assets

Revision ID: n1c2d3e4f5g6
Revises: m0b1c2d3e4f5
Create Date: 2026-10-21 11:10:00
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "n1c2d3e4f5g6"
down_revision: Union[str, Sequence[str], None] = "m0b1c2d3e4f5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("lineage_edge") as batch:
        batch.add_column(sa.Column("asset_id", sa.Integer(), nullable=True))
        batch.create_index("ix_lineage_edge_asset_id", ["asset_id"])
    op.execute(
        "update lineage_edge set asset_id = cast(to_id as integer) "
        "where to_type = 'asset' and asset_id is null")
    op.execute(
        "update lineage_edge set asset_id = cast(from_id as integer) "
        "where from_type = 'asset' and asset_id is null")
    # column edges are regenerated on the next publish
    op.execute("delete from lineage_edge where from_column is not null")


def downgrade() -> None:
    with op.batch_alter_table("lineage_edge") as batch:
        batch.drop_index("ix_lineage_edge_asset_id")
        batch.drop_column("asset_id")
