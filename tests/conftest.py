import os
import uuid
from collections.abc import AsyncIterator, Iterator
from pathlib import Path
from typing import Final

import pytest
from alembic import command
from alembic.config import Config
from service_kit.api.testing import request_id  # noqa: F401
from service_kit.logging.testing import configure_test_logger  # noqa: F401
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import URL, make_url

from competitor_pulse.configuration import DatabaseConfiguration
from competitor_pulse.database import Database

DATABASE_URL = "postgresql://postgres:postgres@localhost:5432/competitor_pulse"


def pytest_addoption(parser):
    parser.addoption(
        "--show-logs", action="store_true", default=False, help="Show logs in the console"
    )


@pytest.fixture
def anyio_backend() -> str:
    # Async tests (@pytest.mark.anyio) run on asyncio, like the app.
    return "asyncio"


@pytest.fixture(autouse=True)
def database_environment(monkeypatch: pytest.MonkeyPatch):
    # Dummy values so the app's configuration loads; tests never reach a real database.
    # No idle connections, so the pool doesn't try to connect when the app starts.
    monkeypatch.setenv("CP_DATABASE_URL", DATABASE_URL)
    monkeypatch.setenv("CP_DATABASE_POOL_MIN_SIZE", "0")


# --- Real PostgreSQL ---
# Set CP_TEST_DATABASE_URL to a server you can create databases on, for example the one from
# docker compose: postgresql://postgres:postgres@localhost:5432/postgres. Each test gets its own
# new database, which is dropped afterwards. Without the variable these tests are skipped.

TEST_DATABASE_URL_ENV_KEY: Final = "CP_TEST_DATABASE_URL"
PYPROJECT_PATH: Final = Path(__file__).parents[1] / "pyproject.toml"


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
    # The app's setting is a plain postgresql:// URL (psycopg rejects the +psycopg form).
    plain_url = url.set(drivername="postgresql").render_as_string(hide_password=False)
    monkeypatch.setenv("CP_DATABASE_URL", plain_url)
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


@pytest.fixture
async def migrated_database(migrated_engine: Engine) -> AsyncIterator[Database]:
    """The app's Database (psycopg pool, async engine) on the migrated test database."""
    database = Database.from_configuration(DatabaseConfiguration())  # type: ignore[call-arg]
    await database.open()
    yield database
    await database.close()
