import pytest
from service_kit.api.testing import request_id  # noqa: F401
from service_kit.logging.testing import configure_test_logger  # noqa: F401

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
