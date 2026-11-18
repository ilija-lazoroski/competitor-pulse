import asyncio

import pytest

from competitor_pulse.configuration import CleanerConfiguration
from competitor_pulse.poller.cleaner import Cleaner
from tests.poller.retention_repository.spy_retention_repository import SpyRetentionRepository

pytestmark = pytest.mark.anyio

CONFIG = CleanerConfiguration(retention_days=90, interval_seconds=3600, batch_size=3)


async def test_old_snapshots_are_deleted_in_batches_then_removed_competitors():
    repository = SpyRetentionRepository(old_snapshots=7, removed_competitors=2)

    deleted = await Cleaner(repository, CONFIG).clean()

    assert repository.deleted_batches == [3, 3, 1]
    assert deleted == (7, 2)


async def test_a_full_last_batch_is_followed_by_an_empty_one():
    repository = SpyRetentionRepository(old_snapshots=6)

    await Cleaner(repository, CONFIG).clean()

    assert repository.deleted_batches == [3, 3, 0]


async def test_a_failed_round_is_retried_after_the_interval():
    repository = SpyRetentionRepository(old_snapshots=2, failures=1)
    sleeps: list[float] = []

    async def sleep(seconds: float) -> None:
        sleeps.append(seconds)
        if len(sleeps) == 2:
            raise asyncio.CancelledError

    with pytest.raises(asyncio.CancelledError):
        await Cleaner(repository, CONFIG, sleep=sleep).run()

    assert sleeps == [3600, 3600]
    assert repository.deleted_batches == [2]
