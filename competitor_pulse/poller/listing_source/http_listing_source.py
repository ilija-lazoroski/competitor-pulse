import asyncio
from http import HTTPStatus

import httpx2 as httpx

from competitor_pulse.configuration import SourceConfiguration
from competitor_pulse.models import Listing
from competitor_pulse.poller.listing_source.errors import (
    ListingNotFoundError,
    SourceConnectionError,
    SourceHTTPError,
    SourceInvalidBodyError,
    SourceRateLimitedError,
    SourceTimeoutError,
)
from competitor_pulse.poller.listing_source.listing_parser import parse_listing
from competitor_pulse.poller.listing_source.listing_source import ListingSource
from competitor_pulse.types import CompetitorID


class HTTPListingSource(ListingSource):
    """The ListingSource over HTTP: GET <base_url>/listings/<id>, one request per fetch.

    It never retries: every request counts against the source's global rate limit, so the
    poller decides when to try again.
    """

    def __init__(self, client: httpx.AsyncClient, timeout_seconds: float):
        self._client = client
        self._timeout_seconds = timeout_seconds

    @classmethod
    def from_configuration(cls, config: SourceConfiguration) -> "HTTPListingSource":
        """Creates the source with its own HTTP client; close() closes the client.

        :param config: The listing source settings
        :returns: The source, ready to fetch
        """
        client = httpx.AsyncClient(base_url=str(config.base_url), timeout=config.timeout_seconds)
        return cls(client, config.timeout_seconds)

    async def fetch(self, competitor_id: CompetitorID) -> Listing:
        """Fetches a competitor's current listing with a single request.

        :param competitor_id: The competitor whose listing to fetch
        :returns: The listing; fields the source left out or sent unreadable are in
                  missing_fields
        :raises ListingNotFoundError: If the source does not list the competitor
        :raises SourceRateLimitedError: If the source rate limits the request
        :raises SourceHTTPError: If the source answers with another unexpected status
        :raises SourceTimeoutError: If the source does not answer in time
        :raises SourceConnectionError: If the source cannot be reached or the request fails
        :raises SourceInvalidBodyError: If the source answers 200 without a JSON object
        """
        try:
            # httpx's own timeout applies to each phase (connect, every read, ...), so a source
            # that sends its answer slowly could take far longer; this bounds the whole request.
            async with asyncio.timeout(self._timeout_seconds):
                response = await self._client.get(f"/listings/{competitor_id}")
        except (httpx.TimeoutException, TimeoutError) as err:
            raise SourceTimeoutError(self._timeout_seconds) from err
        except httpx.RequestError as err:
            # Every other way the request can fail (connection, protocol, decoding, ...).
            raise SourceConnectionError(str(err) or type(err).__name__) from err

        match response.status_code:
            case HTTPStatus.OK:
                return _parse_body(response)
            case HTTPStatus.NOT_FOUND:
                raise ListingNotFoundError(competitor_id)
            case HTTPStatus.TOO_MANY_REQUESTS:
                raise SourceRateLimitedError(_retry_after_seconds(response))
            case status:
                raise SourceHTTPError(status)

    async def close(self) -> None:
        """Closes the HTTP client and its connections."""
        await self._client.aclose()


def _parse_body(response: httpx.Response) -> Listing:
    """Reads a 200 response's JSON object into a listing.

    :param response: The source's 200 response
    :returns: The listing
    :raises SourceInvalidBodyError: If the body is not a JSON object
    """
    try:
        body = response.json()
    except ValueError as err:
        raise SourceInvalidBodyError("the body is not JSON") from err
    if not isinstance(body, dict):
        raise SourceInvalidBodyError(f"expected a JSON object, got {type(body).__name__}")
    return parse_listing(body)


def _retry_after_seconds(response: httpx.Response) -> float | None:
    """Reads the Retry-After header of a 429 response.

    :param response: The source's 429 response
    :returns: The seconds to wait, or None if the header is missing or not a number of seconds
    """
    try:
        return max(float(response.headers["retry-after"]), 0)
    except (KeyError, ValueError):
        return None
