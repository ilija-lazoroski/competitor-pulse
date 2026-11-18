from collections.abc import Iterator
from datetime import UTC, datetime
from http import HTTPStatus

import pytest
from fastapi.testclient import TestClient

from competitor_pulse.app.dependencies import competitor_repository
from competitor_pulse.app.main import app
from competitor_pulse.models import ChangeView, Snapshot
from competitor_pulse.types import ListingField, PollOutcome, SummaryStatus
from tests.app.competitor_repository.in_memory_competitor_repository import (
    InMemoryCompetitorRepository,
)

SNAPSHOT = Snapshot(
    id=7,
    fetched_at=datetime(2026, 9, 10, 12, tzinfo=UTC),
    outcome=PollOutcome.OK,
    error=None,
    title="Acme CRM",
    tagline="Simple CRM for small teams",
    price="$29/mo",
    description="Track leads and deals in one place.",
    changed=True,
    changes={ListingField.PRICE: ChangeView(old="$39/mo", new="$29/mo")},
    summary="Price dropped from $39/mo to $29/mo.",
    summary_status=SummaryStatus.READY,
    summary_error=None,
)


@pytest.fixture
def repository() -> Iterator[InMemoryCompetitorRepository]:
    fake = InMemoryCompetitorRepository()
    app.dependency_overrides[competitor_repository] = lambda: fake
    yield fake


# --- the brief's JSON contract ---


def test_competitors_are_listed_in_camel_case(
    api_client: TestClient, repository: InMemoryCompetitorRepository
):
    repository.track("acme-crm")

    response = api_client.get("/api/competitors")

    assert response.status_code == HTTPStatus.OK
    assert response.json() == [
        {
            "id": "acme-crm",
            "createdAt": "2026-09-01T00:00:00Z",
            "lastChangedAt": None,
            "changedRecently": False,
        }
    ]


def test_snapshots_are_listed_in_camel_case(
    api_client: TestClient, repository: InMemoryCompetitorRepository
):
    repository.track("acme-crm", snapshots=[SNAPSHOT])

    response = api_client.get("/api/competitors/acme-crm/snapshots")

    assert response.status_code == HTTPStatus.OK
    assert response.json() == [
        {
            "id": 7,
            "fetchedAt": "2026-09-10T12:00:00Z",
            "outcome": "ok",
            "error": None,
            "title": "Acme CRM",
            "tagline": "Simple CRM for small teams",
            "price": "$29/mo",
            "description": "Track leads and deals in one place.",
            "changed": True,
            "changes": {"price": {"old": "$39/mo", "new": "$29/mo"}},
            "summary": "Price dropped from $39/mo to $29/mo.",
            "summaryStatus": "ready",
            "summaryError": None,
        }
    ]


def test_snapshots_pass_limit_and_cursor(
    api_client: TestClient, repository: InMemoryCompetitorRepository
):
    repository.track("acme-crm")

    api_client.get("/api/competitors/acme-crm/snapshots?limit=10&before=7")

    assert repository.snapshot_requests == [("acme-crm", 10, 7)]


# --- success statuses ---


def test_add_competitor(api_client: TestClient, repository: InMemoryCompetitorRepository):
    response = api_client.post("/api/competitors", json={"id": "acme-crm"})

    assert response.status_code == HTTPStatus.CREATED
    assert response.json() == {"id": "acme-crm"}
    assert repository.is_tracked("acme-crm")


def test_remove_competitor(api_client: TestClient, repository: InMemoryCompetitorRepository):
    repository.track("acme-crm")

    response = api_client.delete("/api/competitors/acme-crm")

    assert response.status_code == HTTPStatus.NO_CONTENT
    assert not repository.is_tracked("acme-crm")


# --- repository errors become HTTP errors ---


def test_already_tracked_is_a_conflict(
    api_client: TestClient, repository: InMemoryCompetitorRepository
):
    repository.track("acme-crm")

    response = api_client.post("/api/competitors", json={"id": "acme-crm"})

    assert response.status_code == HTTPStatus.CONFLICT
    assert response.json()["message"] == "Competitor 'acme-crm' is already tracked"
    assert response.json()["competitor_id"] == "acme-crm"


@pytest.mark.parametrize(
    ("method", "path"),
    [("DELETE", "/api/competitors/acme-crm"), ("GET", "/api/competitors/acme-crm/snapshots")],
)
def test_not_tracked_is_not_found(
    api_client: TestClient, repository: InMemoryCompetitorRepository, method: str, path: str
):
    response = api_client.request(method, path)

    assert response.status_code == HTTPStatus.NOT_FOUND
    assert response.json()["message"] == "Competitor 'acme-crm' is not tracked"


def test_page_size_above_maximum_is_rejected(
    api_client: TestClient, repository: InMemoryCompetitorRepository
):
    repository.track("acme-crm")

    response = api_client.get("/api/competitors/acme-crm/snapshots?limit=201")

    assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT
    assert response.json()["message"] == "limit must not be larger than 200"


# --- competitor ids ---


@pytest.mark.parametrize("competitor_id", ["a", "acme-crm", "crm2", "a" * 64])
def test_valid_ids_are_accepted(
    api_client: TestClient, repository: InMemoryCompetitorRepository, competitor_id: str
):
    response = api_client.post("/api/competitors", json={"id": competitor_id})

    assert response.status_code == HTTPStatus.CREATED


@pytest.mark.parametrize(
    "competitor_id",
    ["", "Acme-CRM", "-acme", "acme-", "acme crm", "../control", "acme/crm", "a" * 65],
)
def test_invalid_ids_are_rejected(
    api_client: TestClient, repository: InMemoryCompetitorRepository, competitor_id: str
):
    response = api_client.post("/api/competitors", json={"id": competitor_id})

    assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT


@pytest.mark.parametrize(
    ("method", "path"),
    [("DELETE", "/api/competitors/Acme"), ("GET", "/api/competitors/acme-/snapshots")],
)
def test_invalid_id_in_path_is_rejected(
    api_client: TestClient, repository: InMemoryCompetitorRepository, method: str, path: str
):
    response = api_client.request(method, path)

    assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT
