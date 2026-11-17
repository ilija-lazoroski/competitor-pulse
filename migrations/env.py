"""Alembic environment: migrates the database at CP_DATABASE_URL."""

import logging

from alembic import context
from sqlalchemy import create_engine, pool

from competitor_pulse.configuration import DatabaseConfiguration
from competitor_pulse.database import to_sqlalchemy_url
from competitor_pulse.tables import metadata

logging.basicConfig(level=logging.WARNING, format="%(levelname)-5.5s [%(name)s] %(message)s")
logging.getLogger("alembic").setLevel(logging.INFO)


def run_migrations_online() -> None:
    config = DatabaseConfiguration()  # type: ignore[call-arg]
    engine = create_engine(
        to_sqlalchemy_url(config.url),
        poolclass=pool.NullPool,
        connect_args={"connect_timeout": config.connect_timeout_seconds},
    )

    with engine.connect() as connection:
        # `alembic revision --autogenerate` compares the database with these tables.
        context.configure(connection=connection, target_metadata=metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    raise SystemExit("Offline mode (--sql) is not supported; run migrations against a database.")

run_migrations_online()
