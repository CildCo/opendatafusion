"""favorites, alert notes and column glossary links

Revision ID: b8c9d0e1f2a3
Revises: f6a7b8c9d0e1
Create Date: 2026-11-26
"""
import sqlalchemy as sa
from alembic import op

revision = "b8c9d0e1f2a3"
down_revision = "f6a7b8c9d0e1"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "favorite",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(),
                  sa.ForeignKey("project.id"), nullable=False),
        sa.Column("user_id", sa.Integer(),
                  sa.ForeignKey("app_user.id"), nullable=False),
        sa.Column("object_type", sa.String(length=32), nullable=False),
        sa.Column("object_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("project_id", "user_id", "object_type",
                            "object_id", name="uq_favorite_owner_object"),
    )
    op.create_index("ix_favorite_project_id", "favorite", ["project_id"])
    op.create_index("ix_favorite_user_id", "favorite", ["user_id"])
    op.create_index("ix_favorite_created_at", "favorite", ["created_at"])

    op.create_table(
        "alert_note",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(),
                  sa.ForeignKey("project.id"), nullable=False),
        sa.Column("alert_id", sa.BigInteger(),
                  sa.ForeignKey("alert.id"), nullable=False),
        sa.Column("actor", sa.String(length=64), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_alert_note_project_id", "alert_note",
                    ["project_id"])
    op.create_index("ix_alert_note_alert_id", "alert_note", ["alert_id"])
    op.create_index("ix_alert_note_created_at", "alert_note",
                    ["created_at"])
    op.create_index("ix_alert_note_alert_created", "alert_note",
                    ["alert_id", "created_at"])

    op.create_table(
        "column_term",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(),
                  sa.ForeignKey("project.id"), nullable=False),
        sa.Column("dataset_id", sa.Integer(),
                  sa.ForeignKey("dataset.id"), nullable=False),
        sa.Column("column_name", sa.String(length=128), nullable=False),
        sa.Column("term_id", sa.Integer(),
                  sa.ForeignKey("glossary_term.id"), nullable=False),
        sa.Column("created_by", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("dataset_id", "column_name", "term_id",
                            name="uq_column_term_link"),
    )
    op.create_index("ix_column_term_project_id", "column_term",
                    ["project_id"])
    op.create_index("ix_column_term_dataset_id", "column_term",
                    ["dataset_id"])
    op.create_index("ix_column_term_term_id", "column_term", ["term_id"])

    with op.batch_alter_table("alert") as batch:
        batch.add_column(sa.Column("assigned_to", sa.String(length=64),
                                   nullable=True))
        batch.add_column(sa.Column("acked_by", sa.String(length=64),
                                   nullable=True))
        batch.add_column(sa.Column("closed_by", sa.String(length=64),
                                   nullable=True))
        batch.create_index("ix_alert_assigned_to", ["assigned_to"])


def downgrade():
    with op.batch_alter_table("alert") as batch:
        batch.drop_index("ix_alert_assigned_to")
        batch.drop_column("closed_by")
        batch.drop_column("acked_by")
        batch.drop_column("assigned_to")
    op.drop_table("column_term")
    op.drop_table("alert_note")
    op.drop_table("favorite")
