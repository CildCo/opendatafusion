from logging.config import fileConfig

from alembic import context

from odf.db import Base, engine
from odf import models  # noqa: F401  (register tables)

config = context.config
if config.config_file_name:
    fileConfig(config.config_file_name)
target_metadata = Base.metadata


def run_migrations_online():
    with engine.connect() as conn:
        context.configure(connection=conn, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


run_migrations_online()
