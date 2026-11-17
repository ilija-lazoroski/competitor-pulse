import asyncio
from contextlib import suppress
from datetime import UTC, datetime

import pytest

from competitor_pulse.configuration import PollerConfiguration
from competitor_pulse.listing_source import (
    ListingNotFoundError,
    SourceRateLimitedError,
    SourceTimeoutError,
)
from competitor_pulse.models import Listing, PollResult
from competitor_pulse.poller.poller import Poller
from competitor_pulse.poller.rate_limiter import RateLimiter
from competitor_pulse.types import CompetitorId, PollOutcome
from tests.listing_source.fake_listing_source import FakeListingSource
from tests.poll_repository.fake_poll_repository import FakePollRepository

pytestmark = pytest.mark.anyio

FETCHED_AT = datetime(2026, 9, 10, 12, tzinfo=UTC)
CONFIG = PollerConfiguration(
    interval_seconds=900,
    requests_per_second=1000,
    max_in_flight=5,
    claim_batch_size=2,
    idle_seconds=0.01,
    rate_limited_pause_seconds=3,
)
LISTING = Listing(
    title="Acme CRM",
    tagline="Simple CRM for small teams",
    price=None,
    description="Track leads and deals in one place.",
    missing_fields=[],
)


class RecordingRateLimiter(RateLimiter):
    def __init__(self) -> None:
        super().__init__(1000)
        self.pauses: list[float] = []

    def pause(self, seconds: float) -> None:
        self.pauses.append(seconds)


def poller(
    repository: FakePollRepository,
    source: FakeListingSource,
    limiter: RateLimiter | None = None,
) -> Poller:
    return Poller(
        repository, source, limiter or RecordingRateLimiter(), CONFIG, clock=lambda: FETCHED_AT
    )


def outcomes(repository: FakePollRepository) -> dict[str, PollOutcome]:
    return {competitor_id: result.outcome for competitor_id, result in repository.saved}


async def test_listing_is_saved_as_a_snapshot():
    repository = FakePollRepository()
    repository.tracked.add("acme-crm")

    await poller(repository, FakeListingSource({"acme-crm": LISTING})).poll("acme-crm")

    assert repository.saved == [
        (
            "acme-crm",
            PollResult(fetched_at=FETCHED_AT, outcome=PollOutcome.OK, error=None, listing=LISTING),
        )
    ]


async def test_source_errors_are_saved_as_snapshots():
    repository = FakePollRepository()
    repository.tracked.add("gone")
    repository.tracked.add("slow")
    source = FakeListingSource(
        {"gone": ListingNotFoundError("gone"), "slow": SourceTimeoutError(10)}
    )

    await poller(repository, source).poll("gone")
    await poller(repository, source).poll("slow")

    assert outcomes(repository) == {"gone": PollOutcome.NOT_FOUND, "slow": PollOutcome.FAILED}


@pytest.mark.parametrize(("retry_after", "pause"), [(5, 5), (None, 3)])
async def test_rate_limited_poll_is_requeued_and_pauses_requests(
    retry_after: float | None, pause: float
):
    repository = FakePollRepository()
    repository.tracked.add("acme-crm")
    limiter = RecordingRateLimiter()
    source = FakeListingSource({"acme-crm": SourceRateLimitedError(retry_after)})

    await poller(repository, source, limiter).poll("acme-crm")

    assert repository.saved == []
    assert repository.requeued == ["acme-crm"]
    assert limiter.pauses == [pause]


async def test_run_polls_every_due_competitor_and_survives_a_failing_save():
    class FailingSaveRepository(FakePollRepository):
        async def save_poll(self, competitor_id: CompetitorId, result: PollResult) -> bool:
            if competitor_id == "broken":
                raise ConnectionError("database is down")
            return await super().save_poll(competitor_id, result)

    repository = FailingSaveRepository()
    for competitor_id in ["acme-crm", "broken", "orbit-hr"]:
        repository.tracked.add(competitor_id)
    repository.due = ["acme-crm", "broken", "orbit-hr"]
    source = FakeListingSource({id_: LISTING for id_ in repository.due})

    running = asyncio.create_task(poller(repository, source).run())
    while len(source.fetched) < 3 or len(repository.saved) < 2:
        await asyncio.sleep(0.01)
    running.cancel()
    with suppress(asyncio.CancelledError):
        await running

    assert source.fetched == ["acme-crm", "broken", "orbit-hr"]
    assert outcomes(repository) == {"acme-crm": PollOutcome.OK, "orbit-hr": PollOutcome.OK}
