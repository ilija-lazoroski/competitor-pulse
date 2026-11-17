from datetime import timedelta
from typing import Any

from sqlalchemy import exists, func, select
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from competitor_pulse.errors import poll_error_adapter
from competitor_pulse.models import PollResult
from competitor_pulse.poll_repository.poll_repository import PollRepository
from competitor_pulse.tables import competitors, is_tracked, snapshots
from competitor_pulse.types import CompetitorId, PollOutcome, SummaryStatus

_has_listing = snapshots.c.outcome.in_([PollOutcome.OK, PollOutcome.INCOMPLETE])


class PostgresPollRepository(PollRepository):
    """The PollRepository on PostgreSQL, with SQLAlchemy Core."""

    def __init__(self, engine: AsyncEngine):
        self._engine = engine

    async def claim_due(self, limit: int, interval: timedelta) -> list[CompetitorId]:
        # SKIP LOCKED: competitors another transaction is claiming or saving are left alone.
        due = (
            select(competitors.c.id)
            .where(is_tracked, competitors.c.next_poll_at <= func.now())
            .order_by(competitors.c.next_poll_at)
            .limit(limit)
            .with_for_update(skip_locked=True)
            .cte("due")
        )
        claim = (
            competitors.update()
            .where(competitors.c.id.in_(select(due.c.id)))
            .values(next_poll_at=func.now() + interval)
            .returning(competitors.c.id)
        )
        async with self._engine.begin() as connection:
            return list((await connection.execute(claim)).scalars())

    async def requeue(self, competitor_id: CompetitorId) -> None:
        async with self._engine.begin() as connection:
            await connection.execute(
                competitors.update()
                .where(competitors.c.id == competitor_id, is_tracked)
                .values(next_poll_at=func.now())
            )

    async def save_poll(self, competitor_id: CompetitorId, result: PollResult) -> bool:
        async with self._engine.begin() as connection:
            if not await self._lock_tracked(connection, competitor_id):
                return False

            had_listing = await connection.scalar(
                select(exists().where(snapshots.c.competitor_id == competitor_id, _has_listing))
            )
            await connection.execute(
                snapshots.insert().values(
                    competitor_id=competitor_id,
                    **_snapshot_values(result, first_listing=not had_listing),
                )
            )
            return True

    @staticmethod
    async def _lock_tracked(connection: AsyncConnection, competitor_id: CompetitorId) -> bool:
        """Locks a tracked competitor's row against every other writer until the transaction ends.

        :param connection: The connection whose transaction holds the lock
        :param competitor_id: The competitor to lock
        :returns: True if locked; False if the competitor is not tracked
        """
        tracked = await connection.execute(
            select(competitors.c.id)
            .where(competitors.c.id == competitor_id, is_tracked)
            .with_for_update()
        )
        return tracked.first() is not None


def _snapshot_values(result: PollResult, first_listing: bool) -> dict[str, Any]:
    """Builds the snapshot columns of a poll.

    Until change detection exists, a listing is a baseline when it is the competitor's first
    and unchanged otherwise.

    :param result: What the poll found
    :param first_listing: True if the competitor has no earlier snapshot with a listing
    :returns: The snapshot's column values, without the competitor id
    """
    listing = result.listing
    price = listing.price if listing else None
    if result.outcome in (PollOutcome.OK, PollOutcome.INCOMPLETE):
        summary_status = SummaryStatus.BASELINE if first_listing else SummaryStatus.NO_CHANGE
    else:
        summary_status = SummaryStatus.POLL_FAILED
    return {
        "fetched_at": result.fetched_at,
        "outcome": result.outcome,
        "error": (
            poll_error_adapter.dump_python(result.error, mode="json") if result.error else None
        ),
        "title": listing.title if listing else None,
        "tagline": listing.tagline if listing else None,
        "price_amount": price.amount if price else None,
        "price_currency": price.currency if price else None,
        "price_period": price.period if price else None,
        "price_unit": price.unit if price else None,
        "description": listing.description if listing else None,
        "changed": False,
        "changes": None,
        "summary": None,
        "summary_status": summary_status,
        "summary_error": None,
    }
