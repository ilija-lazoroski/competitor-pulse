import asyncio
from contextlib import suppress

import pytest

from competitor_pulse.configuration import LLMConfiguration
from competitor_pulse.errors import SummaryHTTPError, SummaryTimeout, SummaryUnusableAnswer
from competitor_pulse.models import PendingSummary
from competitor_pulse.poller.llm_client import LLMHTTPError, LLMTimeoutError, LLMUnusableAnswerError
from competitor_pulse.poller.summarizer import Summarizer
from competitor_pulse.poller.summary_prompt import build_prompt
from competitor_pulse.types import FieldChange, ListingField
from tests.poller.summary_repository.fake_summary_repository import FakeSummaryRepository

pytestmark = pytest.mark.anyio

CONFIG = LLMConfiguration(
    max_attempts=3, retry_backoff_seconds=0, max_in_flight=2, idle_seconds=0.01
)


def change(snapshot_id: int) -> PendingSummary:
    return PendingSummary(
        snapshot_id=snapshot_id,
        competitor_id="acme-crm",
        changes={ListingField.TITLE: FieldChange(old="Acme CRM", new="Acme CRM Pro")},
    )


class FakeLLM:
    """Gives the answers in order: a text is returned, an exception is raised."""

    def __init__(self, *answers: str | Exception):
        self._answers = list(answers)
        self.prompts: list[str] = []

    async def complete(self, instructions: str, prompt: str) -> str:
        self.prompts.append(prompt)
        answer = self._answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer


async def test_summary_is_stored():
    repository = FakeSummaryRepository([change(1)])
    llm = FakeLLM("The title is now Acme CRM Pro.")

    await Summarizer(repository, llm, CONFIG).summarize(change(1))

    assert repository.summaries == {1: "The title is now Acme CRM Pro."}
    assert llm.prompts == [build_prompt("acme-crm", change(1).changes, CONFIG.max_field_chars)]


async def test_failed_call_is_retried_and_each_attempt_counts_against_the_cap():
    repository = FakeSummaryRepository([change(1)])
    llm = FakeLLM(LLMHTTPError(500), LLMTimeoutError(60), "The title is now Acme CRM Pro.")

    await Summarizer(repository, llm, CONFIG).summarize(change(1))

    assert repository.summaries == {1: "The title is now Acme CRM Pro."}
    assert repository.reservations == 3


async def test_failure_after_the_last_attempt_is_stored():
    repository = FakeSummaryRepository([change(1)])
    llm = FakeLLM(LLMHTTPError(500), LLMHTTPError(503), LLMTimeoutError(60))

    await Summarizer(repository, llm, CONFIG).summarize(change(1))

    assert repository.failures == {
        1: (SummaryTimeout(message="The LLM did not answer within 60s", after_seconds=60), False)
    }


@pytest.mark.parametrize("status", [400, 401, 403, 404, 422])
async def test_http_error_that_would_fail_again_is_stored_without_another_attempt(status: int):
    repository = FakeSummaryRepository([change(1)])
    llm = FakeLLM(LLMHTTPError(status))

    await Summarizer(repository, llm, CONFIG).summarize(change(1))

    assert repository.failures == {
        1: (
            SummaryHTTPError(message=f"The LLM answered with HTTP {status}", status=status),
            False,
        )
    }
    assert repository.reservations == 1


@pytest.mark.parametrize("status", [408, 429, 500, 502, 503])
async def test_http_error_that_can_pass_is_retried(status: int):
    repository = FakeSummaryRepository([change(1)])
    llm = FakeLLM(LLMHTTPError(status), "The title is now Acme CRM Pro.")

    await Summarizer(repository, llm, CONFIG).summarize(change(1))

    assert repository.summaries == {1: "The title is now Acme CRM Pro."}
    assert repository.reservations == 2


async def test_unusable_answer_is_stored_without_another_attempt():
    repository = FakeSummaryRepository([change(1)])
    llm = FakeLLM(LLMUnusableAnswerError("the answer is empty"))

    await Summarizer(repository, llm, CONFIG).summarize(change(1))

    error, unusable = repository.failures[1]
    assert isinstance(error, SummaryUnusableAnswer) and unusable
    assert repository.reservations == 1


async def test_reaching_the_cap_marks_every_waiting_change():
    repository = FakeSummaryRepository([change(1), change(2), change(3)], calls_left=0)
    llm = FakeLLM()

    await Summarizer(repository, llm, CONFIG).summarize(change(1))

    assert llm.prompts == []
    assert repository.cap_reached == {1, 2, 3}


async def test_cap_reached_between_attempts_keeps_the_failure_out():
    repository = FakeSummaryRepository([change(1)], calls_left=1)
    llm = FakeLLM(LLMHTTPError(500))

    await Summarizer(repository, llm, CONFIG).summarize(change(1))

    assert repository.cap_reached == {1}
    assert repository.failures == {}


async def test_run_summarizes_every_pending_change_and_survives_a_failing_save():
    class FailingSaveRepository(FakeSummaryRepository):
        async def save_summary(self, snapshot_id: int, summary: str) -> None:
            if snapshot_id == 2:
                raise ConnectionError("database is down")
            await super().save_summary(snapshot_id, summary)

    repository = FailingSaveRepository([change(1), change(2), change(3)])
    llm = FakeLLM(*[f"Summary {n}" for n in range(10)])

    running = asyncio.create_task(Summarizer(repository, llm, CONFIG).run())
    while len(repository.summaries) < 2:
        await asyncio.sleep(0.01)
    running.cancel()
    with suppress(asyncio.CancelledError):
        await running

    assert set(repository.summaries) == {1, 3}
