import pytest

from competitor_pulse.poller.rate_limiter import RateLimiter

pytestmark = pytest.mark.anyio


class FakeTime:
    """A clock that only moves when the limiter sleeps."""

    def __init__(self) -> None:
        self.now = 1000.0
        self.sleeps: list[float] = []

    def clock(self) -> float:
        return self.now

    async def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


def limiter(time: FakeTime, requests_per_second: float = 4) -> RateLimiter:
    return RateLimiter(requests_per_second, clock=time.clock, sleep=time.sleep)


async def test_requests_are_spaced_evenly():
    time = FakeTime()
    rate_limiter = limiter(time)

    for _ in range(5):
        await rate_limiter.acquire()

    assert time.sleeps == [0.25, 0.25, 0.25, 0.25]


async def test_unused_time_is_not_saved_up_for_a_burst():
    time = FakeTime()
    rate_limiter = limiter(time)
    await rate_limiter.acquire()

    time.now += 60
    for _ in range(3):
        await rate_limiter.acquire()

    assert time.sleeps == [0.25, 0.25]


async def test_pause_holds_back_the_next_request():
    time = FakeTime()
    rate_limiter = limiter(time)
    await rate_limiter.acquire()

    rate_limiter.pause(2)
    await rate_limiter.acquire()
    await rate_limiter.acquire()

    assert time.sleeps == [2, 0.25]


async def test_short_pause_does_not_shorten_the_spacing():
    time = FakeTime()
    rate_limiter = limiter(time)
    await rate_limiter.acquire()

    rate_limiter.pause(0.1)
    await rate_limiter.acquire()

    assert time.sleeps == [0.25]
