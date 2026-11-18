from datetime import UTC, datetime

from competitor_pulse.app.competitor_repository import (
    CompetitorAlreadyTrackedError,
    CompetitorNotTrackedError,
    InvalidPageSizeError,
)
from competitor_pulse.models import Competitor, Snapshot
from competitor_pulse.types import CompetitorID

CREATED_AT = datetime(2026, 9, 1, tzinfo=UTC)
MAX_PAGE_SIZE = 200


class FakeCompetitorRepository:
    """In memory, raising the same errors as the real one. Snapshots are returned as given."""

    def __init__(self) -> None:
        self._tracked: dict[str, Competitor] = {}
        self._snapshots: dict[str, list[Snapshot]] = {}
        self.snapshot_requests: list[tuple[str, int | None, int | None]] = []

    def track(self, competitor_id: str, snapshots: list[Snapshot] | None = None) -> None:
        self._tracked[competitor_id] = Competitor(
            id=competitor_id, created_at=CREATED_AT, last_changed_at=None, changed_recently=False
        )
        self._snapshots[competitor_id] = snapshots or []

    def is_tracked(self, competitor_id: str) -> bool:
        return competitor_id in self._tracked

    async def list_tracked(self) -> list[Competitor]:
        return [self._tracked[id_] for id_ in sorted(self._tracked)]

    async def add(self, competitor_id: CompetitorID) -> None:
        if competitor_id in self._tracked:
            raise CompetitorAlreadyTrackedError(competitor_id)
        self.track(competitor_id)

    async def remove(self, competitor_id: CompetitorID) -> None:
        if self._tracked.pop(competitor_id, None) is None:
            raise CompetitorNotTrackedError(competitor_id)

    async def list_snapshots(
        self, competitor_id: CompetitorID, limit: int | None, before_id: int | None
    ) -> list[Snapshot]:
        if limit is not None and limit > MAX_PAGE_SIZE:
            raise InvalidPageSizeError(limit, MAX_PAGE_SIZE)
        if competitor_id not in self._tracked:
            raise CompetitorNotTrackedError(competitor_id)
        self.snapshot_requests.append((competitor_id, limit, before_id))
        return self._snapshots[competitor_id]
