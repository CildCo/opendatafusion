"""api studio interface import

Revision ID: d4e5f6a7b8c9
Revises: c7a1f0e2b9d4
Create Date: 2026-10-20 13:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text
from sqlalchemy.orm import Session

from odf.apistudio.interface_import import import_interface_records

revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, Sequence[str], None] = 'c7a1f0e2b9d4'
branch_labels = None
depends_on = None


def upgrade() -> None:
    session = Session(bind=op.get_bind())
    import_interface_records(session, commit=False)
    session.close()


def downgrade() -> None:
    op.get_bind().execute(text(
        "delete from asset_version where asset_id in ("
        "select id from asset where type='api' and owner='system' "
        "and key in (select interface_key from data_interface))"))
    op.get_bind().execute(text(
        "delete from asset where type='api' and owner='system' "
        "and key in (select interface_key from data_interface)"))
