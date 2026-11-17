from typing import Protocol

from competitor_pulse.errors import CompetitorPulseError
from competitor_pulse.models import Competitor, Snapshot
from competitor_pulse.types import CompetitorId


class CompetitorNotTrackedError(CompetitorPulseError):
    def __init__(self, competitor_id: str):
        super().__init__(
            f"Competitor {competitor_id!r} is not tracked", competitor_id=competitor_id
        )


class CompetitorAlreadyTrackedError(CompetitorPulseError):
    def __init__(self, competitor_id: str):
        super().__init__(
            f"Competitor {competitor_id!r} is already tracked", competitor_id=competitor_id
        )


class InvalidPageSizeError(CompetitorPulseError):
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
        """The tracked competitors, ordered by id, with whether they changed recently."""
        ...

    async def add(self, competitor_id: CompetitorId) -> None:
        """Starts tracking a competitor; a removed one is restored with its history.

        :raises CompetitorAlreadyTrackedError: If it is tracked already
        """
        ...

    async def remove(self, competitor_id: CompetitorId) -> None:
        """Stops tracking a competitor and keeps its history.

        :raises CompetitorNotTrackedError: If it is not tracked
        """
        ...

    async def list_snapshots(
        self, competitor_id: CompetitorId, limit: int | None, before_id: int | None
    ) -> list[Snapshot]:
        """Newest first; with `before_id`, only snapshots older than that one.

        :param limit: Page size; None for the configured default
        :raises CompetitorNotTrackedError: If the competitor is not tracked
        :raises InvalidPageSizeError: If `limit` is above the configured maximum
        """
        ...
