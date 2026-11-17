"""Tests that need a real PostgreSQL.

Set CP_TEST_DATABASE_URL to a server you can create databases on, for example the one from
docker compose: postgresql://postgres:postgres@localhost:5432/postgres. Each test gets its own
new database, which is dropped afterwards. Without the variable these tests are skipped.
"""

import os
import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import Final

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import URL, make_url

TEST_DATABASE_URL_ENV_KEY: Final = "CP_TEST_DATABASE_URL"
PYPROJECT_PATH: Final = Path(__file__).parents[2] / "pyproject.toml"


@pytest.fixture
def database_url(monkeypatch: pytest.MonkeyPatch) -> Iterator[URL]:
    """A new, empty database; CP_DATABASE_URL points at it while the test runs."""
    server_url = os.environ.get(TEST_DATABASE_URL_ENV_KEY)
    if not server_url:
        pytest.skip(f"{TEST_DATABASE_URL_ENV_KEY} is not set")

    server = make_url(server_url).set(drivername="postgresql+psycopg")
    name = f"cp_test_{uuid.uuid4().hex[:12]}"
    admin = create_engine(server, isolation_level="AUTOCOMMIT")
    with admin.connect() as connection:
        connection.execute(text(f'CREATE DATABASE "{name}"'))

    url = server.set(database=name)
    monkeypatch.setenv("CP_DATABASE_URL", url.render_as_string(hide_password=False))
    try:
        yield url
    finally:
        with admin.connect() as connection:
            connection.execute(text(f'DROP DATABASE "{name}" WITH (FORCE)'))
        admin.dispose()


@pytest.fixture
def alembic_config() -> Config:
    return Config(toml_file=PYPROJECT_PATH)


@pytest.fixture
def engine(database_url: URL) -> Iterator[Engine]:
    engine = create_engine(database_url)
    yield engine
    engine.dispose()


@pytest.fixture
def migrated_engine(alembic_config: Config, engine: Engine) -> Engine:
    command.upgrade(alembic_config, "head")
    return engine
