import asyncio
from collections.abc import Awaitable, Callable
from datetime import timedelta

from service_kit.logging import logger

from competitor_pulse.configuration import CleanerConfiguration
from competitor_pulse.poller.retention_repository import RetentionRepository


class Cleaner:
    """Deletes snapshots older than the retention period, and the competitors they leave behind."""

    def __init__(
        self,
        repository: RetentionRepository,
        config: CleanerConfiguration,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ):
        self._repository = repository
        self._config = config
        self._retention = timedelta(days=config.retention_days)
        self._sleep = sleep

    async def run(self) -> None:
        """Cleans once per interval, until cancelled; a failed round is logged and retried."""
        while True:
            try:
                await self.clean()
            except Exception as err:
                logger.error("Cleaning old history failed", error=str(err))
            await self._sleep(self._config.interval_seconds)

    async def clean(self) -> tuple[int, int]:
        """Deletes everything older than the retention period, in short batches.

        :returns: How many snapshots and how many removed competitors were deleted
        """
        snapshots = 0
        while True:
            deleted = await self._repository.delete_snapshots_older_than(
                self._retention, self._config.batch_size
            )
            snapshots += deleted
            if deleted < self._config.batch_size:
                break

        competitors = await self._repository.delete_removed_competitors_older_than(self._retention)
        if snapshots or competitors:
            logger.info("Deleted old history", snapshots=snapshots, competitors=competitors)
        return snapshots, competitors
