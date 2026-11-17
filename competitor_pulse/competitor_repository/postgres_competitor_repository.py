from datetime import timedelta

from sqlalchemy import Row, false, func, select, tuple_
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from competitor_pulse.competitor_repository.competitor_repository import CompetitorRepository
from competitor_pulse.competitor_repository.errors import (
    CompetitorAlreadyTrackedError,
    CompetitorNotTrackedError,
    InvalidPageSizeError,
)
from competitor_pulse.configuration import ApiConfiguration
from competitor_pulse.formatting import format_price
from competitor_pulse.models import Competitor, Snapshot
from competitor_pulse.tables import competitors, snapshots
from competitor_pulse.types import CompetitorId, Price

_tracked = competitors.c.removed_at.is_(None)


class PostgresCompetitorRepository(CompetitorRepository):
    """The CompetitorRepository on PostgreSQL, with SQLAlchemy Core."""

    def __init__(self, engine: AsyncEngine, config: ApiConfiguration):
        self._engine = engine
        self._recent_change_window = timedelta(hours=config.recent_change_hours)
        self._page_size = config.snapshots_page_size
        self._max_page_size = config.snapshots_max_page_size

    async def list_tracked(self) -> list[Competitor]:
        # The database clock decides what "recent" is, like it sets last_changed_at.
        changed_recently = func.coalesce(
            competitors.c.last_changed_at >= func.now() - self._recent_change_window, false()
        )
        query = (
            select(
                competitors.c.id,
                competitors.c.created_at,
                competitors.c.last_changed_at,
                changed_recently.label("changed_recently"),
            )
            .where(_tracked)
            .order_by(competitors.c.id)
        )
        async with self._engine.connect() as connection:
            rows = await connection.execute(query)
            return [Competitor.model_validate(row._mapping) for row in rows]

    async def add(self, competitor_id: CompetitorId) -> None:
        async with self._engine.begin() as connection:
            created = await connection.execute(
                insert(competitors)
                .values(id=competitor_id)
                .on_conflict_do_nothing(index_elements=[competitors.c.id])
                .returning(competitors.c.id)
            )
            if created.first():
                return

            restored = await connection.execute(
                competitors.update()
                .where(competitors.c.id == competitor_id, competitors.c.removed_at.is_not(None))
                .values(removed_at=None)
                .returning(competitors.c.id)
            )
            if not restored.first():
                raise CompetitorAlreadyTrackedError(competitor_id)

    async def remove(self, competitor_id: CompetitorId) -> None:
        async with self._engine.begin() as connection:
            removed = await connection.execute(
                competitors.update()
                .where(competitors.c.id == competitor_id, _tracked)
                .values(removed_at=func.now())
                .returning(competitors.c.id)
            )
            if not removed.first():
                raise CompetitorNotTrackedError(competitor_id)

    async def list_snapshots(
        self, competitor_id: CompetitorId, limit: int | None, before_id: int | None
    ) -> list[Snapshot]:
        if limit is not None and limit > self._max_page_size:
            raise InvalidPageSizeError(limit, self._max_page_size)

        query = (
            select(
                snapshots,
                snapshots.c.error["message"].astext.label("error_message"),
                snapshots.c.summary_error["message"].astext.label("summary_error_message"),
            )
            .where(snapshots.c.competitor_id == competitor_id)
            .order_by(snapshots.c.fetched_at.desc(), snapshots.c.id.desc())
            .limit(limit or self._page_size)
        )
        if before_id is not None:
            # Keyset paging: rows after the cursor in (fetched_at, id) order. If the cursor is
            # not one of this competitor's snapshots, the comparison is NULL: an empty page.
            cursor = snapshots.alias("cursor")
            cursor_position = (
                select(cursor.c.fetched_at, cursor.c.id)
                .where(cursor.c.id == before_id, cursor.c.competitor_id == competitor_id)
                .scalar_subquery()
            )
            query = query.where(tuple_(snapshots.c.fetched_at, snapshots.c.id) < cursor_position)

        async with self._engine.begin() as connection:
            await self._lock_tracked(connection, competitor_id)
            rows = await connection.execute(query)
            return [_to_snapshot(row) for row in rows]

    @staticmethod
    async def _lock_tracked(connection: AsyncConnection, competitor_id: CompetitorId) -> None:
        """Locks a tracked competitor's row, so a removal waits until the transaction ends.

        :param connection: The connection whose transaction holds the lock
        :param competitor_id: The competitor to lock
        :raises CompetitorNotTrackedError: If the competitor is not tracked
        """
        tracked = await connection.execute(
            select(competitors.c.id)
            .where(competitors.c.id == competitor_id, _tracked)
            .with_for_update(read=True)
        )
        if not tracked.first():
            raise CompetitorNotTrackedError(competitor_id)


def _to_snapshot(row: Row) -> Snapshot:
    """Builds the API's snapshot from a row of the snapshots query.

    :param row: A snapshots row with the error and summary error messages
    :returns: The snapshot, with the price formatted
    """
    values = row._mapping
    price = None
    if values["price_amount"] is not None:
        price = format_price(
            Price(
                amount=values["price_amount"],
                currency=values["price_currency"],
                period=values["price_period"],
                unit=values["price_unit"],
            )
        )
    return Snapshot(
        id=values["id"],
        fetched_at=values["fetched_at"],
        outcome=values["outcome"],
        error=values["error_message"],
        title=values["title"],
        tagline=values["tagline"],
        price=price,
        description=values["description"],
        changed=values["changed"],
        summary=values["summary"],
        summary_status=values["summary_status"],
        summary_error=values["summary_error_message"],
    )
