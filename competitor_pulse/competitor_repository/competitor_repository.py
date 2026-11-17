from typing import Protocol

from competitor_pulse.errors import CompetitorPulseError
from competitor_pulse.models import Competitor, Snapshot
from competitor_pulse.types import CompetitorId


class CompetitorNotTrackedError(CompetitorPulseError):
    """The competitor is not tracked: it was never added, or it was removed."""

    def __init__(self, competitor_id: str):
        super().__init__(
            f"Competitor {competitor_id!r} is not tracked", competitor_id=competitor_id
        )


class CompetitorAlreadyTrackedError(CompetitorPulseError):
    """The competitor is tracked already, so it cannot be added again."""

    def __init__(self, competitor_id: str):
        super().__init__(
            f"Competitor {competitor_id!r} is already tracked", competitor_id=competitor_id
        )


class InvalidPageSizeError(CompetitorPulseError):
    """The requested page size is above the configured maximum."""

    def __init__(self, limit: int, max_page_size: int):
        super().__init__(
            f"limit must not be larger than {max_page_size}",
            limit=limit,
            max_page_size=max_page_size,
        )


class CompetitorRepository(Protocol):
    """Tracked competitors and their snapshots.

    A removed competitor is not tracked: it is left out everywhere until it is added again.
    """

    async def list_tracked(self) -> list[Competitor]:
        """Lists the tracked competitors.

        :returns: The tracked competitors, ordered by id, with whether they changed recently
        """
        ...

    async def add(self, competitor_id: CompetitorId) -> None:
        """Starts tracking a competitor; a removed one is restored with its history.

        :param competitor_id: The competitor to track
        :raises CompetitorAlreadyTrackedError: If the competitor is tracked already
        """
        ...

    async def remove(self, competitor_id: CompetitorId) -> None:
        """Stops tracking a competitor and keeps its history.

        :param competitor_id: The competitor to stop tracking
        :raises CompetitorNotTrackedError: If the competitor is not tracked
        """
        ...

    async def list_snapshots(
        self, competitor_id: CompetitorId, limit: int | None, before_id: int | None
    ) -> list[Snapshot]:
        """Lists one page of a competitor's snapshots, newest first.

        :param competitor_id: The competitor whose snapshots to list
        :param limit: The page size; None for the configured default
        :param before_id: Only snapshots older than this snapshot; None for the newest page
        :returns: At most `limit` snapshots, newest first
        :raises CompetitorNotTrackedError: If the competitor is not tracked
        :raises InvalidPageSizeError: If `limit` is above the configured maximum
        """
        ...
