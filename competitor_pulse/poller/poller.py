import asyncio
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from service_kit.logging import logger

from competitor_pulse.configuration import PollerConfiguration
from competitor_pulse.poller import poll_result
from competitor_pulse.poller.listing_source import (
    ListingSource,
    SourceError,
    SourceRateLimitedError,
)
from competitor_pulse.poller.poll_repository import PollRepository
from competitor_pulse.poller.rate_limiter import RateLimiter
from competitor_pulse.types import CompetitorID


def _utc_now() -> datetime:
    return datetime.now(UTC)


class Poller:
    """Polls every tracked competitor in turn and stores each poll as a snapshot.

    All requests share one rate limiter, so there must be only one poller per source.
    """

    def __init__(
        self,
        repository: PollRepository,
        source: ListingSource,
        limiter: RateLimiter,
        config: PollerConfiguration,
        clock: Callable[[], datetime] = _utc_now,
    ):
        self._repository = repository
        self._source = source
        self._limiter = limiter
        self._config = config
        self._interval = timedelta(seconds=config.interval_seconds)
        self._clock = clock
        self._in_flight = asyncio.Semaphore(config.max_in_flight)

    async def run(self) -> None:
        """Claims due competitors and polls them, until cancelled.

        A poll starts when the rate limiter allows it, without waiting for earlier polls to
        finish, so a slow answer does not hold up the others.
        """
        async with asyncio.TaskGroup() as polls:
            while True:
                due = await self._claim_due()
                if not due:
                    await asyncio.sleep(self._config.idle_seconds)
                    continue
                for competitor_id in due:
                    await self._in_flight.acquire()
                    await self._limiter.acquire()
                    polls.create_task(self._poll_and_release(competitor_id))

    async def poll(self, competitor_id: CompetitorID) -> None:
        """Fetches one competitor's listing and stores what happened as a snapshot.

        A 429 is not stored: the competitor goes back in the queue and every request pauses, for
        the Retry-After but at most the configured maximum.

        :param competitor_id: The competitor to poll
        """
        try:
            listing = await self._source.fetch(competitor_id)
        except SourceRateLimitedError as err:
            pause = min(
                err.retry_after_seconds or self._config.rate_limited_pause_seconds,
                self._config.max_rate_limited_pause_seconds,
            )
            logger.warning(
                "The source is rate limiting; pausing",
                pause_seconds=pause,
                retry_after_seconds=err.retry_after_seconds,
            )
            self._limiter.pause(pause)
            await self._repository.requeue(competitor_id)
            return
        except SourceError as err:
            result = poll_result.from_error(err, self._clock())
        else:
            result = poll_result.from_listing(listing, self._clock())

        if not await self._repository.save_poll(competitor_id, result):
            logger.info("Poll dropped: competitor removed meanwhile", competitor_id=competitor_id)

    async def _claim_due(self) -> list[CompetitorID]:
        """Claims the next batch of due competitors; none if the database fails.

        :returns: The claimed competitors' ids
        """
        try:
            return await self._repository.claim_due(self._config.claim_batch_size, self._interval)
        except Exception as err:
            logger.error("Claiming due competitors failed", error=str(err))
            return []

    async def _poll_and_release(self, competitor_id: CompetitorID) -> None:
        """Polls one competitor, logs any failure and frees its in-flight slot.

        :param competitor_id: The competitor to poll
        """
        try:
            await self.poll(competitor_id)
        except Exception as err:
            # The competitor is already scheduled for its next poll; one lost poll is logged.
            logger.error("Poll failed", competitor_id=competitor_id, error=str(err))
        finally:
            self._in_flight.release()
