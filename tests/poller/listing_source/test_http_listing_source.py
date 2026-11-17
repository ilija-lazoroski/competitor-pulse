from collections.abc import Callable
from decimal import Decimal

import httpx2 as httpx
import pytest

from competitor_pulse.poller.listing_source import (
    HttpListingSource,
    ListingNotFoundError,
    SourceConnectionError,
    SourceHttpError,
    SourceInvalidBodyError,
    SourceRateLimitedError,
    SourceTimeoutError,
)
from competitor_pulse.types import ListingField, Price, PricePeriod

pytestmark = pytest.mark.anyio

TIMEOUT_SECONDS = 10
BODY = {
    "id": "acme-crm",
    "title": "  Acme CRM ",
    "tagline": "Simple&nbsp;CRM for small teams",
    "price": "USD 29 per month",
    "description": "Track leads &amp; deals in one place.",
    "requestId": "0f3c",
    "viewerCount": 77,
}


def source(handler: Callable[[httpx.Request], httpx.Response]) -> HttpListingSource:
    client = httpx.AsyncClient(
        base_url="http://source.test", transport=httpx.MockTransport(handler)
    )
    return HttpListingSource(client, TIMEOUT_SECONDS)


def answer(response: httpx.Response) -> HttpListingSource:
    return source(lambda _request: response)


def fail_with(error: Exception) -> HttpListingSource:
    def handler(request: httpx.Request) -> httpx.Response:
        raise error

    return source(handler)


async def test_listing_is_fetched_from_the_listings_path():
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=BODY)

    listing = await source(handler).fetch("acme-crm")

    assert [str(r.url) for r in requests] == ["http://source.test/listings/acme-crm"]
    assert listing.title == "Acme CRM"
    assert listing.price == Price(
        amount=Decimal("29.00"), currency="USD", period=PricePeriod.MONTH, unit=None
    )
    assert listing.missing_fields == []


async def test_incomplete_listing_is_returned_with_its_missing_fields():
    listing = await answer(httpx.Response(200, json={**BODY, "price": None})).fetch("acme-crm")

    assert listing.title == "Acme CRM"
    assert listing.missing_fields == [ListingField.PRICE]


async def test_not_found():
    with pytest.raises(ListingNotFoundError):
        await answer(httpx.Response(404, json={"error": "not_found"})).fetch("acme-crm")


@pytest.mark.parametrize(
    ("headers", "retry_after_seconds"),
    [
        ({"retry-after": "1"}, 1),
        ({"retry-after": "2.5"}, 2.5),
        ({}, None),
        ({"retry-after": "soon"}, None),
    ],
)
async def test_rate_limited(headers: dict[str, str], retry_after_seconds: float | None):
    response = httpx.Response(429, headers=headers, json={"error": "rate_limited"})

    with pytest.raises(SourceRateLimitedError) as err:
        await answer(response).fetch("acme-crm")

    assert err.value.retry_after_seconds == retry_after_seconds


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(500, json={"error": "internal_error"}),
        httpx.Response(503, json={"error": "service_unavailable"}),
        httpx.Response(502, text="<html><body><h1>502 Bad Gateway</h1></body></html>"),
        httpx.Response(301, headers={"location": "/elsewhere"}),
    ],
)
async def test_unexpected_status(response: httpx.Response):
    with pytest.raises(SourceHttpError) as err:
        await answer(response).fetch("acme-crm")

    assert err.value.status == response.status_code


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(200, text="<html>Acme CRM</html>"),
        httpx.Response(200, json=["Acme CRM"]),
        httpx.Response(200, json="Acme CRM"),
    ],
)
async def test_body_that_is_not_a_json_object(response: httpx.Response):
    with pytest.raises(SourceInvalidBodyError):
        await answer(response).fetch("acme-crm")


async def test_timeout():
    with pytest.raises(SourceTimeoutError) as err:
        await fail_with(httpx.ReadTimeout("no answer")).fetch("acme-crm")

    assert err.value.after_seconds == TIMEOUT_SECONDS


@pytest.mark.parametrize(
    "error",
    [httpx.ConnectError("connection refused"), httpx.RemoteProtocolError("connection closed")],
)
async def test_connection_error(error: Exception):
    with pytest.raises(SourceConnectionError):
        await fail_with(error).fetch("acme-crm")
