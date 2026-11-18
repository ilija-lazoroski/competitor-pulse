from typing import Protocol

from competitor_pulse.models import Listing
from competitor_pulse.types import CompetitorID


class ListingSource(Protocol):
    """Fetches competitors' current listings."""

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
        ...
