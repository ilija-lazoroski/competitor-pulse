from collections.abc import Collection

from sqlalchemy import cast, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.types import Date

from competitor_pulse.errors import SummaryFailure, summary_failure_adapter
from competitor_pulse.models import PendingSummary
from competitor_pulse.poller.summary_repository.summary_repository import SummaryRepository
from competitor_pulse.tables import llm_usage, snapshots
from competitor_pulse.types import SummaryStatus, changes_adapter

_pending = snapshots.c.summary_status == SummaryStatus.PENDING


class PostgresSummaryRepository(SummaryRepository):
    """The SummaryRepository on PostgreSQL, with SQLAlchemy Core."""

    def __init__(self, engine: AsyncEngine):
        self._engine = engine

    async def pending(self, limit: int, exclude: Collection[int]) -> list[PendingSummary]:
        query = (
            select(snapshots.c.id, snapshots.c.competitor_id, snapshots.c.changes)
            .where(_pending, snapshots.c.id.not_in(exclude))
            .order_by(snapshots.c.fetched_at.desc(), snapshots.c.id.desc())
            .limit(limit)
        )
        async with self._engine.connect() as connection:
            rows = await connection.execute(query)
            return [
                PendingSummary(
                    snapshot_id=row.id,
                    competitor_id=row.competitor_id,
                    changes=changes_adapter.validate_python(row.changes),
                )
                for row in rows
            ]

    async def reserve_llm_call(self, daily_cap: int) -> bool:
        if daily_cap < 1:
            return False
        # One statement, so concurrent reservations can never go past the cap together.
        today = cast(func.timezone("UTC", func.now()), Date)
        reserve = (
            insert(llm_usage)
            .values(day=today, calls=1)
            .on_conflict_do_update(
                index_elements=[llm_usage.c.day],
                set_={"calls": llm_usage.c.calls + 1},
                where=llm_usage.c.calls < daily_cap,
            )
            .returning(llm_usage.c.calls)
        )
        async with self._engine.begin() as connection:
            return (await connection.execute(reserve)).first() is not None

    async def save_summary(self, snapshot_id: int, summary: str) -> None:
        async with self._engine.begin() as connection:
            await connection.execute(
                snapshots.update()
                .where(snapshots.c.id == snapshot_id, _pending)
                .values(summary=summary, summary_status=SummaryStatus.READY)
            )

    async def save_failure(self, snapshot_id: int, error: SummaryFailure, unusable: bool) -> None:
        status = SummaryStatus.LLM_UNUSABLE if unusable else SummaryStatus.LLM_FAILED
        async with self._engine.begin() as connection:
            await connection.execute(
                snapshots.update()
                .where(snapshots.c.id == snapshot_id, _pending)
                .values(
                    summary_status=status,
                    summary_error=summary_failure_adapter.dump_python(error, mode="json"),
                )
            )

    async def mark_cap_reached(self, exclude: Collection[int]) -> int:
        async with self._engine.begin() as connection:
            marked = await connection.execute(
                snapshots.update()
                .where(_pending, snapshots.c.id.not_in(exclude))
                .values(summary_status=SummaryStatus.CAP_REACHED)
            )
            return marked.rowcount
