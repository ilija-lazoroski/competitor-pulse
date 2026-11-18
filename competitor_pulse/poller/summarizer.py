import asyncio

from service_kit.logging import logger

from competitor_pulse.configuration import LLMConfiguration
from competitor_pulse.errors import summary_failure_adapter
from competitor_pulse.models import PendingSummary
from competitor_pulse.poller.llm_client import (
    LLMClient,
    LLMError,
    LLMHTTPError,
    LLMUnusableAnswerError,
)
from competitor_pulse.poller.summary_prompt import INSTRUCTIONS, build_prompt
from competitor_pulse.poller.summary_repository import SummaryRepository


class Summarizer:
    """Asks the LLM to summarize each change that waits for a summary, newest first.

    It runs apart from polling, so a slow or failing LLM never holds up a poll; a change shows
    as pending until its summary, or the reason for not having one, is stored.
    """

    def __init__(self, repository: SummaryRepository, llm: LLMClient, config: LLMConfiguration):
        self._repository = repository
        self._llm = llm
        self._config = config
        self._in_flight: set[int] = set()
        self._slots = asyncio.Semaphore(config.max_in_flight)

    async def run(self) -> None:
        """Summarizes pending changes as they come, until cancelled."""
        async with asyncio.TaskGroup() as calls:
            while True:
                pending = await self._next_pending()
                if not pending:
                    await asyncio.sleep(self._config.idle_seconds)
                    continue
                for change in pending:
                    await self._slots.acquire()
                    self._in_flight.add(change.snapshot_id)
                    calls.create_task(self._summarize_and_release(change))

    async def summarize(self, change: PendingSummary) -> None:
        """Gets one change's summary from the LLM and stores it, or why there is none.

        Every attempt counts against the daily cap. Unusable answers and HTTP errors that would
        fail the same way again (4xx other than 408 and 429) are not retried; other failures
        are, up to the configured number of attempts. When the cap is reached, every
        change still waiting is marked as over the cap.

        :param change: The change to summarize
        """
        prompt = build_prompt(change.competitor_id, change.changes, self._config.max_field_chars)
        for attempt in range(1, self._config.max_attempts + 1):
            if not await self._repository.reserve_llm_call(self._config.daily_cap):
                marked = await self._repository.mark_cap_reached(
                    exclude=self._others_in_flight(change)
                )
                logger.warning("The daily LLM cap is reached", marked=marked)
                return
            try:
                summary = await self._llm.complete(INSTRUCTIONS, prompt)
            except LLMUnusableAnswerError as err:
                await self._store_failure(change, err, unusable=True)
                return
            except LLMError as err:
                # A 4xx like a wrong key or an unknown model fails the same way every time.
                retryable = not isinstance(err, LLMHTTPError) or err.retryable
                if not retryable or attempt == self._config.max_attempts:
                    await self._store_failure(change, err, unusable=False)
                    return
                logger.info("LLM call failed; trying again", attempt=attempt, error=err.message)
                await asyncio.sleep(self._config.retry_backoff_seconds * attempt)
            else:
                await self._repository.save_summary(change.snapshot_id, summary)
                return

    async def _next_pending(self) -> list[PendingSummary]:
        """Lists pending changes that are not being summarized already; none if the database fails.

        :returns: The next changes to summarize
        """
        try:
            return await self._repository.pending(self._config.max_in_flight, self._in_flight)
        except Exception as err:
            logger.error("Listing pending summaries failed", error=str(err))
            return []

    async def _store_failure(self, change: PendingSummary, err: LLMError, unusable: bool) -> None:
        """Stores why a change gets no summary.

        :param change: The change
        :param err: Why the LLM gave no summary
        :param unusable: True if the LLM answered with something unusable
        """
        logger.warning("No summary", snapshot_id=change.snapshot_id, error=err.message)
        record = summary_failure_adapter.validate_python(err.structured_error)
        await self._repository.save_failure(change.snapshot_id, record, unusable)

    def _others_in_flight(self, change: PendingSummary) -> set[int]:
        """The snapshots other calls are summarizing right now.

        :param change: The change this call is about
        :returns: Their snapshot ids, without this change's
        """
        return self._in_flight - {change.snapshot_id}

    async def _summarize_and_release(self, change: PendingSummary) -> None:
        """Summarizes one change, logs any failure and frees its slot.

        :param change: The change to summarize
        """
        try:
            await self.summarize(change)
        except Exception as err:
            # The change stays pending and is tried again on a later round.
            logger.error("Summarizing failed", snapshot_id=change.snapshot_id, error=str(err))
        finally:
            self._in_flight.discard(change.snapshot_id)
            self._slots.release()
