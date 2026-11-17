from http import HTTPStatus

import pytest
from fastapi.testclient import TestClient

from competitor_pulse.app.dependencies import database
from competitor_pulse.app.main import app


class FakeDatabase:
    def __init__(self, error: Exception | None = None):
        self._error = error

    async def ping(self) -> None:
        if self._error:
            raise self._error


def use_database(fake: FakeDatabase):
    app.dependency_overrides[database] = lambda: fake


def test_health_returns_ok(api_client: TestClient):
    response = api_client.get("/health")

    assert response.status_code == HTTPStatus.OK
    assert response.json() == {"status": "ok"}


def test_health_db_ok(api_client: TestClient):
    use_database(FakeDatabase())

    response = api_client.get("/health/db")

    assert response.status_code == HTTPStatus.OK
    assert response.json() == {"status": "ok"}


@pytest.mark.parametrize("error", [OSError("connection refused"), TimeoutError()])
def test_health_db_unavailable(api_client: TestClient, error: Exception):
    use_database(FakeDatabase(error))

    response = api_client.get("/health/db")

    assert response.status_code == HTTPStatus.SERVICE_UNAVAILABLE
    assert response.json() == {"status": "unavailable"}
