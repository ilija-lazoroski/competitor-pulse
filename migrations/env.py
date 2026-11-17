"""Alembic environment: migrates the database at CP_DATABASE_URL."""

import logging
import os

from alembic import context
from sqlalchemy import create_engine, pool

from competitor_pulse.configuration import CONFIG_PATH_ENV_KEY, DatabaseConfiguration
from competitor_pulse.database import to_sqlalchemy_url
from competitor_pulse.tables import metadata

logging.basicConfig(level=logging.WARNING, format="%(levelname)-5.5s [%(name)s] %(message)s")
logging.getLogger("alembic").setLevel(logging.INFO)


def run_migrations_online() -> None:
    """Runs the migrations against the database at CP_DATABASE_URL, in one transaction.

    The database settings come from CP_DATABASE_* environment variables or the .env file at
    CP_CONFIG_PATH, like the API's and the poller's.

    :raises ValidationError: If a database setting is missing or invalid
    """
    config_file_path = os.environ.get(CONFIG_PATH_ENV_KEY)
    config = DatabaseConfiguration(_env_file=config_file_path)  # type: ignore[call-arg]
    engine = create_engine(
        to_sqlalchemy_url(config.url),
        poolclass=pool.NullPool,
        connect_args={"connect_timeout": config.connect_timeout_seconds},
    )

    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    raise SystemExit("Offline mode (--sql) is not supported; run migrations against a database.")

run_migrations_online()
