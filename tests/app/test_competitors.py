from http import HTTPStatus

import pytest
from fastapi.testclient import TestClient


def test_unknown_route_returns_404(api_client: TestClient):
    response = api_client.get("/does-not-exist")

    assert response.status_code == HTTPStatus.NOT_FOUND


@pytest.mark.parametrize(
    ("method", "path", "body"),
    [
        ("GET", "/api/competitors", None),
        ("POST", "/api/competitors", {"id": "acme-crm"}),
        ("DELETE", "/api/competitors/acme-crm", None),
        ("GET", "/api/competitors/acme-crm/snapshots", None),
    ],
)
def test_stub_endpoints_return_501(
    api_client: TestClient, method: str, path: str, body: dict | None
):
    response = api_client.request(method, path, json=body)

    assert response.status_code == HTTPStatus.NOT_IMPLEMENTED


@pytest.mark.parametrize("competitor_id", ["a", "acme-crm", "crm2", "a" * 64])
def test_valid_ids_are_accepted(api_client: TestClient, competitor_id: str):
    response = api_client.post("/api/competitors", json={"id": competitor_id})

    # Past validation; the endpoint itself is still a stub.
    assert response.status_code == HTTPStatus.NOT_IMPLEMENTED


@pytest.mark.parametrize(
    "competitor_id",
    ["", "Acme-CRM", "-acme", "acme-", "acme crm", "../control", "acme/crm", "a" * 65],
)
def test_invalid_ids_are_rejected(api_client: TestClient, competitor_id: str):
    response = api_client.post("/api/competitors", json={"id": competitor_id})

    assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT


def test_missing_id_is_rejected(api_client: TestClient):
    response = api_client.post("/api/competitors", json={})

    assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT


@pytest.mark.parametrize(
    ("method", "path"),
    [("DELETE", "/api/competitors/Acme"), ("GET", "/api/competitors/acme-/snapshots")],
)
def test_invalid_id_in_path_is_rejected(api_client: TestClient, method: str, path: str):
    response = api_client.request(method, path)

    assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT
