from datetime import timedelta

from sqlalchemy import exists, func, select
from sqlalchemy.ext.asyncio import AsyncEngine

from competitor_pulse.poller.retention_repository.retention_repository import RetentionRepository
from competitor_pulse.tables import competitors, snapshots


class PostgresRetentionRepository(RetentionRepository):
    """The RetentionRepository on PostgreSQL, with SQLAlchemy Core."""

    def __init__(self, engine: AsyncEngine):
        self._engine = engine

    async def delete_snapshots_older_than(self, retention: timedelta, limit: int) -> int:
        # The age is measured against the database clock.
        oldest = (
            select(snapshots.c.id)
            .where(snapshots.c.fetched_at < func.now() - retention)
            .limit(limit)
        )
        async with self._engine.begin() as connection:
            deleted = await connection.execute(snapshots.delete().where(snapshots.c.id.in_(oldest)))
            return deleted.rowcount

    async def delete_removed_competitors_older_than(self, retention: timedelta) -> int:
        # The conditions are part of the DELETE, so a competitor added again in between stays.
        has_snapshots = exists().where(snapshots.c.competitor_id == competitors.c.id)
        async with self._engine.begin() as connection:
            deleted = await connection.execute(
                competitors.delete().where(
                    competitors.c.removed_at.is_not(None),
                    competitors.c.removed_at < func.now() - retention,
                    ~has_snapshots,
                )
            )
            return deleted.rowcount
