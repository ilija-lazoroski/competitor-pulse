from collections.abc import Collection
from typing import Protocol

from competitor_pulse.errors import SummaryError
from competitor_pulse.models import PendingSummary


class SummaryRepository(Protocol):
    """The changes waiting for a summary, their summaries, and the LLM's daily cap."""

    async def pending(self, limit: int, exclude: Collection[int]) -> list[PendingSummary]:
        """Lists changes that wait for a summary, newest first.

        :param limit: The most changes to list
        :param exclude: Snapshot ids to leave out, like those already being summarized
        :returns: The pending changes
        """
        ...

    async def reserve_llm_call(self, daily_cap: int) -> bool:
        """Counts one LLM call against today's cap (UTC), if the cap allows it.

        :param daily_cap: The most LLM calls per day
        :returns: True if the call may be made; False if today's cap is reached
        """
        ...

    async def save_summary(self, snapshot_id: int, summary: str) -> None:
        """Stores a snapshot's summary, if the snapshot still waits for one.

        :param snapshot_id: The snapshot whose change was summarized
        :param summary: The summary
        """
        ...

    async def save_failure(self, snapshot_id: int, error: SummaryError, unusable: bool) -> None:
        """Stores why a snapshot gets no summary, if the snapshot still waits for one.

        :param snapshot_id: The snapshot whose change could not be summarized
        :param error: Why the LLM gave no summary
        :param unusable: True if the LLM answered with something unusable; False if it failed
        """
        ...

    async def mark_cap_reached(self, exclude: Collection[int]) -> int:
        """Marks every change that waits for a summary as over today's cap.

        :param exclude: Snapshot ids to leave pending, like those already being summarized
        :returns: How many snapshots were marked
        """
        ...
