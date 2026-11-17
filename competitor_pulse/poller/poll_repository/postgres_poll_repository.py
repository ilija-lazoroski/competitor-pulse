from datetime import timedelta
from typing import Any, Final

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from competitor_pulse.errors import poll_error_adapter
from competitor_pulse.models import Listing, PollResult
from competitor_pulse.poller.change_detection import ChangeDecision, decide
from competitor_pulse.poller.poll_repository.poll_repository import PollRepository
from competitor_pulse.tables import competitors, is_tracked, snapshots
from competitor_pulse.types import CompetitorId, PollOutcome, Price, changes_adapter

_LISTING_OUTCOMES: Final = (PollOutcome.OK, PollOutcome.INCOMPLETE)


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

            decision = decide(
                result,
                previous_listing=await self._latest_listing(connection, competitor_id),
                previously_delisted=await self._latest_answer_was_not_found(
                    connection, competitor_id
                ),
            )
            await connection.execute(
                snapshots.insert().values(
                    competitor_id=competitor_id, **_snapshot_values(result, decision)
                )
            )
            if decision.changed:
                await connection.execute(
                    competitors.update()
                    .where(competitors.c.id == competitor_id)
                    .values(
                        last_changed_at=func.greatest(
                            competitors.c.last_changed_at, result.fetched_at
                        )
                    )
                )
            return True

    @staticmethod
    async def _latest_listing(
        connection: AsyncConnection, competitor_id: CompetitorId
    ) -> Listing | None:
        """Reads the listing of the competitor's latest snapshot that has one.

        Snapshots of one competitor are saved one at a time, so the highest id is the latest.

        :param connection: The connection holding the competitor's lock
        :param competitor_id: The competitor
        :returns: The listing, or None if the competitor never had one
        """
        row = (
            await connection.execute(
                select(snapshots)
                .where(
                    snapshots.c.competitor_id == competitor_id,
                    snapshots.c.outcome.in_(_LISTING_OUTCOMES),
                )
                .order_by(snapshots.c.id.desc())
                .limit(1)
            )
        ).first()
        if row is None:
            return None
        values = row._mapping
        price = None
        if values["price_amount"] is not None:
            price = Price(
                amount=values["price_amount"],
                currency=values["price_currency"],
                period=values["price_period"],
                unit=values["price_unit"],
            )
        return Listing(
            title=values["title"],
            tagline=values["tagline"],
            price=price,
            description=values["description"],
            missing_fields=[],
        )

    @staticmethod
    async def _latest_answer_was_not_found(
        connection: AsyncConnection, competitor_id: CompetitorId
    ) -> bool:
        """Tells whether the source did not list the competitor at its latest answered poll.

        Failed polls got no answer, so they are skipped.

        :param connection: The connection holding the competitor's lock
        :param competitor_id: The competitor
        :returns: True if that poll was not found; False if it had a listing or there was none
        """
        outcome = await connection.scalar(
            select(snapshots.c.outcome)
            .where(
                snapshots.c.competitor_id == competitor_id,
                snapshots.c.outcome.in_([*_LISTING_OUTCOMES, PollOutcome.NOT_FOUND]),
            )
            .order_by(snapshots.c.id.desc())
            .limit(1)
        )
        return outcome == PollOutcome.NOT_FOUND

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


def _snapshot_values(result: PollResult, decision: ChangeDecision) -> dict[str, Any]:
    """Builds the snapshot columns of a poll.

    :param result: What the poll found
    :param decision: Whether the poll changed something, and its summary state
    :returns: The snapshot's column values, without the competitor id
    """
    listing = result.listing
    price = listing.price if listing else None
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
        "changed": decision.changed,
        "changes": (
            changes_adapter.dump_python(decision.changes, mode="json")
            if decision.changes is not None
            else None
        ),
        "summary": decision.summary,
        "summary_status": decision.summary_status,
        "summary_error": None,
    }
