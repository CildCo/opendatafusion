"""governance depth: domains, glossary and asset contracts

Revision ID: a4d5e6f7a8b9
Revises: z3c4d5e6f7a8
Create Date: 2026-11-23
"""
import sqlalchemy as sa
from alembic import op

revision = "a4d5e6f7a8b9"
down_revision = "z3c4d5e6f7a8"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "domain",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(),
                  sa.ForeignKey("project.id"), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=False,
                  server_default=""),
        sa.Column("owner", sa.String(length=64), nullable=False,
                  server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.UniqueConstraint("project_id", "name",
                            name="uq_domain_project_name"),
    )
    op.create_table(
        "glossary_term",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(),
                  sa.ForeignKey("project.id"), nullable=False),
        sa.Column("domain_id", sa.Integer(), nullable=True),
        sa.Column("term", sa.String(length=128), nullable=False),
        sa.Column("definition", sa.Text(), nullable=False,
                  server_default=""),
        sa.Column("owner", sa.String(length=64), nullable=False,
                  server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.UniqueConstraint("project_id", "term",
                            name="uq_glossary_project_term"),
    )
    op.add_column("dataset", sa.Column("domain_id", sa.Integer(),
                                       nullable=True))
    op.add_column("asset", sa.Column("domain_id", sa.Integer(),
                                     nullable=True))
    op.add_column("asset", sa.Column("contract_json", sa.JSON(),
                                     nullable=False,
                                     server_default=sa.text("'{}'")))
    op.create_index("ix_dataset_domain", "dataset", ["domain_id"])
    op.create_index("ix_asset_domain", "asset", ["domain_id"])


def downgrade():
    op.drop_index("ix_asset_domain", table_name="asset")
    op.drop_index("ix_dataset_domain", table_name="dataset")
    op.drop_column("asset", "contract_json")
    op.drop_column("asset", "domain_id")
    op.drop_column("dataset", "domain_id")
    op.drop_table("glossary_term")
    op.drop_table("domain")
