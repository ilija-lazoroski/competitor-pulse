from datetime import timedelta

from competitor_pulse.models import PollResult
from competitor_pulse.types import CompetitorId


class FakePollRepository:
    """In memory: claims hand out `due` in order; saves of untracked competitors are dropped."""

    def __init__(self) -> None:
        self.tracked: set[str] = set()
        self.due: list[str] = []
        self.requeued: list[str] = []
        self.saved: list[tuple[str, PollResult]] = []

    async def claim_due(self, limit: int, interval: timedelta) -> list[CompetitorId]:
        claimed, self.due = self.due[:limit], self.due[limit:]
        return claimed

    async def requeue(self, competitor_id: CompetitorId) -> None:
        self.requeued.append(competitor_id)

    async def save_poll(self, competitor_id: CompetitorId, result: PollResult) -> bool:
        if competitor_id not in self.tracked:
            return False
        self.saved.append((competitor_id, result))
        return True
