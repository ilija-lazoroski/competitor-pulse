from datetime import timedelta
from typing import Protocol

from competitor_pulse.models import PollResult
from competitor_pulse.types import CompetitorId


class PollRepository(Protocol):
    """The poll schedule of the tracked competitors, and where their polls are stored."""

    async def claim_due(self, limit: int, interval: timedelta) -> list[CompetitorId]:
        """Takes the tracked competitors that are due for a poll, most overdue first.

        Their next poll moves one interval ahead at once, so no other caller claims them again.

        :param limit: The most competitors to take
        :param interval: How long until each claimed competitor is due again
        :returns: The ids of the claimed competitors
        """
        ...

    async def requeue(self, competitor_id: CompetitorId) -> None:
        """Makes a tracked competitor due again now, after a poll that did not happen.

        :param competitor_id: The competitor to poll again
        """
        ...

    async def save_poll(self, competitor_id: CompetitorId, result: PollResult) -> bool:
        """Stores a poll as the competitor's newest snapshot, with whether it changed anything.

        The poll is compared with the competitor's earlier snapshots; a change also becomes the
        competitor's last change. The competitor's row is locked while saving, so saves of the
        same competitor run one after the other and each one compares with the one before it.

        :param competitor_id: The competitor that was polled
        :param result: What the poll found
        :returns: True if stored; False if the competitor stopped being tracked meanwhile
        """
        ...
