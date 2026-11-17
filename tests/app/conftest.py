from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from competitor_pulse.app.main import app


@pytest.fixture
def api_client() -> Iterator[TestClient]:
    # The context manager runs the app's lifespan (setup/teardown).
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()
