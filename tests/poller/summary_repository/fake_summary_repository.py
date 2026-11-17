from collections.abc import Collection

from competitor_pulse.errors import SummaryError
from competitor_pulse.models import PendingSummary


class FakeSummaryRepository:
    """In memory: a list of pending changes, the calls left today, and what was stored."""

    def __init__(self, pending: list[PendingSummary], calls_left: int = 1000):
        self._pending = {change.snapshot_id: change for change in pending}
        self.calls_left = calls_left
        self.reservations = 0
        self.summaries: dict[int, str] = {}
        self.failures: dict[int, tuple[SummaryError, bool]] = {}
        self.cap_reached: set[int] = set()

    async def pending(self, limit: int, exclude: Collection[int]) -> list[PendingSummary]:
        waiting = [c for id_, c in self._pending.items() if id_ not in exclude]
        return sorted(waiting, key=lambda c: c.snapshot_id, reverse=True)[:limit]

    async def reserve_llm_call(self, daily_cap: int) -> bool:
        if self.calls_left == 0:
            return False
        self.calls_left -= 1
        self.reservations += 1
        return True

    async def save_summary(self, snapshot_id: int, summary: str) -> None:
        if self._pending.pop(snapshot_id, None):
            self.summaries[snapshot_id] = summary

    async def save_failure(self, snapshot_id: int, error: SummaryError, unusable: bool) -> None:
        if self._pending.pop(snapshot_id, None):
            self.failures[snapshot_id] = (error, unusable)

    async def mark_cap_reached(self, exclude: Collection[int]) -> int:
        marked = [id_ for id_ in self._pending if id_ not in exclude]
        for id_ in marked:
            del self._pending[id_]
        self.cap_reached.update(marked)
        return len(marked)
