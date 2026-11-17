import asyncio
import time
from collections.abc import Awaitable, Callable


class RateLimiter:
    """Spaces requests evenly at a fixed rate, shared by every request of the process.

    Requests are spread out rather than sent in bursts, so a source that counts requests per
    second never sees more than the rate. pause() holds everything back, for a 429.
    """

    def __init__(
        self,
        requests_per_second: float,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ):
        self._interval = 1 / requests_per_second
        self._clock = clock
        self._sleep = sleep
        self._next_slot = clock()

    async def acquire(self) -> None:
        """Waits for the next free slot; each call takes one slot."""
        now = self._clock()
        slot = max(now, self._next_slot)
        # Reserve the slot before waiting, so concurrent callers queue behind each other.
        self._next_slot = slot + self._interval
        if slot > now:
            await self._sleep(slot - now)

    def pause(self, seconds: float) -> None:
        """Holds back every request that has not started yet for at least `seconds`.

        :param seconds: How long no request may start, from now
        """
        self._next_slot = max(self._next_slot, self._clock() + seconds)
