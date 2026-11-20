"""job dependency

Revision ID: v8j9k0l1m2n3
Revises: u7i8j9k0l1m2
"""
from alembic import op
import sqlalchemy as sa

revision = "v8j9k0l1m2n3"
down_revision = "u7i8j9k0l1m2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "job_dependency",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(),
                  sa.ForeignKey("project.id"), nullable=False),
        sa.Column("downstream_type", sa.String(length=16), nullable=False),
        sa.Column("downstream_id", sa.Integer(), nullable=False),
        sa.Column("upstream_type", sa.String(length=16), nullable=False),
        sa.Column("upstream_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("project_id", "downstream_type", "downstream_id",
                            "upstream_type", "upstream_id"),
    )
    op.create_index("ix_job_dependency_project_id", "job_dependency",
                    ["project_id"])


def downgrade() -> None:
    op.drop_index("ix_job_dependency_project_id", table_name="job_dependency")
    op.drop_table("job_dependency")
