"""Alembic environment: migrates the database at CP_DATABASE_URL."""

import logging

from alembic import context
from sqlalchemy import create_engine, pool

from competitor_pulse.configuration import DatabaseConfiguration
from competitor_pulse.database import CONNECT_TIMEOUT_SECONDS, to_sqlalchemy_url

logging.basicConfig(level=logging.WARNING, format="%(levelname)-5.5s [%(name)s] %(message)s")
logging.getLogger("alembic").setLevel(logging.INFO)


def run_migrations_online() -> None:
    database_url = to_sqlalchemy_url(DatabaseConfiguration().url)  # type: ignore[call-arg]
    engine = create_engine(
        database_url,
        poolclass=pool.NullPool,
        connect_args={"connect_timeout": CONNECT_TIMEOUT_SECONDS},
    )

    with engine.connect() as connection:
        # The tables (SQLAlchemy Core MetaData) are added with the first schema migration.
        context.configure(connection=connection, target_metadata=None)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    raise SystemExit("Offline mode (--sql) is not supported; run migrations against a database.")

run_migrations_online()
