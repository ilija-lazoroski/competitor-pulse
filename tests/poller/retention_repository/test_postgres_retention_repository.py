from datetime import timedelta
from typing import Any

import pytest
from sqlalchemy import Engine, func, select, text
from sqlalchemy.dialects.postgresql import insert

from competitor_pulse.database import Database
from competitor_pulse.poller.retention_repository import PostgresRetentionRepository
from competitor_pulse.tables import competitors, snapshots

pytestmark = pytest.mark.anyio

RETENTION = timedelta(days=90)
SNAPSHOT: dict[str, Any] = {
    "outcome": "ok",
    "title": "Acme CRM",
    "changed": False,
    "summary_status": "no_change",
}


@pytest.fixture
def repository(migrated_database: Database) -> PostgresRetentionRepository:
    return PostgresRetentionRepository(migrated_database.engine)


def add_competitor(engine: Engine, competitor_id: str, removed_ago: timedelta | None = None):
    with engine.begin() as connection:
        connection.execute(
            insert(competitors).values(
                id=competitor_id,
                removed_at=None if removed_ago is None else func.now() - removed_ago,
            )
        )


def add_snapshots(engine: Engine, competitor_id: str, ages: list[timedelta]):
    with engine.begin() as connection:
        connection.execute(
            snapshots.insert().values(
                [
                    {**SNAPSHOT, "competitor_id": competitor_id, "fetched_at": func.now() - age}
                    for age in ages
                ]
            )
        )


def snapshot_ages_in_days(engine: Engine) -> list[int]:
    with engine.connect() as connection:
        ages = connection.execute(
            text("SELECT extract(day FROM now() - fetched_at)::int FROM snapshots ORDER BY 1")
        )
        return list(ages.scalars())


def competitor_ids(engine: Engine) -> list[str]:
    with engine.connect() as connection:
        return list(
            connection.execute(select(competitors.c.id).order_by(competitors.c.id)).scalars()
        )


async def test_snapshots_older_than_the_retention_are_deleted(
    repository: PostgresRetentionRepository, migrated_engine: Engine
):
    add_competitor(migrated_engine, "acme-crm")
    add_snapshots(migrated_engine, "acme-crm", [timedelta(days=d) for d in (1, 89, 91, 200)])

    deleted = await repository.delete_snapshots_older_than(RETENTION, limit=100)

    assert deleted == 2
    assert snapshot_ages_in_days(migrated_engine) == [1, 89]


async def test_snapshot_deletion_stops_at_the_limit(
    repository: PostgresRetentionRepository, migrated_engine: Engine
):
    add_competitor(migrated_engine, "acme-crm")
    add_snapshots(migrated_engine, "acme-crm", [timedelta(days=100 + d) for d in range(5)])

    assert await repository.delete_snapshots_older_than(RETENTION, limit=2) == 2
    assert len(snapshot_ages_in_days(migrated_engine)) == 3


async def test_only_long_removed_competitors_without_history_are_deleted(
    repository: PostgresRetentionRepository, migrated_engine: Engine
):
    add_competitor(migrated_engine, "removed-long-ago", removed_ago=timedelta(days=91))
    add_competitor(migrated_engine, "removed-with-history", removed_ago=timedelta(days=91))
    add_snapshots(migrated_engine, "removed-with-history", [timedelta(days=10)])
    add_competitor(migrated_engine, "removed-recently", removed_ago=timedelta(days=10))
    add_competitor(migrated_engine, "tracked")

    deleted = await repository.delete_removed_competitors_older_than(RETENTION)

    assert deleted == 1
    assert competitor_ids(migrated_engine) == [
        "removed-recently",
        "removed-with-history",
        "tracked",
    ]
