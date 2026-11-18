from datetime import timedelta
from typing import Any, Final

from sqlalchemy import Row, func, select
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from competitor_pulse.errors import poll_error_adapter
from competitor_pulse.models import ListingValues, PollResult
from competitor_pulse.poller.change_detection import ChangeDecision, decide, remember
from competitor_pulse.poller.poll_repository.poll_repository import PollRepository
from competitor_pulse.tables import competitors, is_tracked, snapshots
from competitor_pulse.types import CompetitorID, PollOutcome, changes_adapter

_LISTING_OUTCOMES: Final = (PollOutcome.OK, PollOutcome.INCOMPLETE)


class PostgresPollRepository(PollRepository):
    """The PollRepository on PostgreSQL, with SQLAlchemy Core."""

    def __init__(self, engine: AsyncEngine):
        self._engine = engine

    async def claim_due(self, limit: int, interval: timedelta) -> list[CompetitorID]:
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

    async def requeue(self, competitor_id: CompetitorID) -> None:
        async with self._engine.begin() as connection:
            await connection.execute(
                competitors.update()
                .where(competitors.c.id == competitor_id, is_tracked)
                .values(next_poll_at=func.now())
            )

    async def save_poll(self, competitor_id: CompetitorID, result: PollResult) -> bool:
        async with self._engine.begin() as connection:
            competitor = await self._lock_tracked(connection, competitor_id)
            if competitor is None:
                return False

            known = (
                ListingValues.model_validate(competitor.known_listing)
                if competitor.known_listing is not None
                else None
            )
            decision = decide(
                result,
                previous_listing=known,
                previously_delisted=await self._latest_answer_was_not_found(
                    connection, competitor_id
                ),
            )
            await connection.execute(
                snapshots.insert().values(
                    competitor_id=competitor_id, **_snapshot_values(result, decision)
                )
            )

            updates: dict[str, Any] = {}
            if result.listing is not None:
                remembered = remember(known, result.listing)
                updates["known_listing"] = (
                    remembered.model_dump(mode="json") if remembered is not None else None
                )
            if decision.changed:
                updates["last_changed_at"] = func.greatest(
                    competitors.c.last_changed_at, result.fetched_at
                )
            if updates:
                await connection.execute(
                    competitors.update().where(competitors.c.id == competitor_id).values(updates)
                )
            return True

    @staticmethod
    async def _latest_answer_was_not_found(
        connection: AsyncConnection, competitor_id: CompetitorID
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
            # The timeline index's order: it finds the competitor's newest rows directly. By id
            # alone, PostgreSQL walks the primary key back through every competitor's rows.
            .order_by(snapshots.c.fetched_at.desc(), snapshots.c.id.desc())
            .limit(1)
        )
        return outcome == PollOutcome.NOT_FOUND

    @staticmethod
    async def _lock_tracked(connection: AsyncConnection, competitor_id: CompetitorID) -> Row | None:
        """Locks a tracked competitor's row against every other writer until the transaction ends.

        :param connection: The connection whose transaction holds the lock
        :param competitor_id: The competitor to lock
        :returns: The competitor's known_listing column; None if the competitor is not tracked
        """
        tracked = await connection.execute(
            select(competitors.c.known_listing)
            .where(competitors.c.id == competitor_id, is_tracked)
            .with_for_update()
        )
        return tracked.first()


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
