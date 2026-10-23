"""oidc subject and totp replay

Revision ID: k8f9a0b1c2d3
Revises: j7e8f9a0b1c2
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "k8f9a0b1c2d3"
down_revision: Union[str, Sequence[str], None] = "j7e8f9a0b1c2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("app_user", sa.Column("totp_last_step", sa.Integer(),
                                        nullable=True))
    op.add_column("app_user", sa.Column("oidc_sub", sa.String(255),
                                        nullable=True))
    op.create_index("ix_app_user_oidc_sub", "app_user", ["oidc_sub"],
                    unique=True)


def downgrade() -> None:
    op.drop_index("ix_app_user_oidc_sub", table_name="app_user")
    op.drop_column("app_user", "oidc_sub")
    op.drop_column("app_user", "totp_last_step")
