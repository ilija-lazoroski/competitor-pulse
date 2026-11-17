from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import Engine, func
from sqlalchemy.dialects.postgresql import insert

from competitor_pulse.app.competitor_repository import (
    CompetitorAlreadyTrackedError,
    CompetitorNotTrackedError,
    InvalidPageSizeError,
    PostgresCompetitorRepository,
)
from competitor_pulse.configuration import ApiConfiguration
from competitor_pulse.database import Database
from competitor_pulse.tables import competitors, snapshots

pytestmark = pytest.mark.anyio

PAGE_SIZE = 3
MAX_PAGE_SIZE = 5
START = datetime(2026, 9, 10, 12, tzinfo=UTC)
SNAPSHOT: dict[str, Any] = {
    "outcome": "ok",
    "title": "Acme CRM",
    "tagline": "Simple CRM for small teams",
    "price_amount": "29.00",
    "price_currency": "USD",
    "price_period": "month",
    "description": "Track leads and deals in one place.",
    "changed": False,
    "summary_status": "no_change",
}


@pytest.fixture
def repository(migrated_database: Database) -> PostgresCompetitorRepository:
    config = ApiConfiguration(
        recent_change_hours=24, snapshots_page_size=PAGE_SIZE, snapshots_max_page_size=MAX_PAGE_SIZE
    )
    return PostgresCompetitorRepository(migrated_database.engine, config)


def insert_snapshots(
    engine: Engine, competitor_id: str, fetched_at: list[datetime], **overrides: Any
) -> list[int]:
    """Tracks the competitor, inserts one snapshot per time in the given order, returns ids."""
    with engine.begin() as connection:
        connection.execute(insert(competitors).values(id=competitor_id).on_conflict_do_nothing())
        rows = [
            {**SNAPSHOT, **overrides, "competitor_id": competitor_id, "fetched_at": at}
            for at in fetched_at
        ]
        return list(
            connection.execute(snapshots.insert().returning(snapshots.c.id), rows).scalars()
        )


def set_last_changed(engine: Engine, competitor_id: str, ago: timedelta | None) -> None:
    with engine.begin() as connection:
        connection.execute(insert(competitors).values(id=competitor_id).on_conflict_do_nothing())
        connection.execute(
            competitors.update()
            .where(competitors.c.id == competitor_id)
            .values(last_changed_at=None if ago is None else func.now() - ago)
        )


async def all_snapshot_ids(repository: PostgresCompetitorRepository, competitor_id: str):
    return [s.id for s in await repository.list_snapshots(competitor_id, MAX_PAGE_SIZE, None)]


# --- tracking ---


async def test_added_competitor_is_listed(repository: PostgresCompetitorRepository):
    await repository.add("acme-crm")

    assert [c.id for c in await repository.list_tracked()] == ["acme-crm"]


async def test_adding_tracked_competitor_fails(repository: PostgresCompetitorRepository):
    await repository.add("acme-crm")

    with pytest.raises(CompetitorAlreadyTrackedError):
        await repository.add("acme-crm")


async def test_removed_competitor_is_not_tracked(repository: PostgresCompetitorRepository):
    await repository.add("acme-crm")

    await repository.remove("acme-crm")

    assert await repository.list_tracked() == []
    with pytest.raises(CompetitorNotTrackedError):
        await repository.list_snapshots("acme-crm", None, None)


@pytest.mark.parametrize("already_removed", [False, True])
async def test_removing_untracked_competitor_fails(
    repository: PostgresCompetitorRepository, already_removed: bool
):
    if already_removed:
        await repository.add("acme-crm")
        await repository.remove("acme-crm")

    with pytest.raises(CompetitorNotTrackedError):
        await repository.remove("acme-crm")


async def test_adding_removed_competitor_restores_its_history(
    repository: PostgresCompetitorRepository, migrated_engine: Engine
):
    [snapshot_id] = insert_snapshots(migrated_engine, "acme-crm", [START])
    await repository.remove("acme-crm")

    await repository.add("acme-crm")

    assert await all_snapshot_ids(repository, "acme-crm") == [snapshot_id]


async def test_list_tracked_is_ordered_by_id(repository: PostgresCompetitorRepository):
    for competitor_id in ["zeta", "acme-crm", "beta"]:
        await repository.add(competitor_id)

    assert [c.id for c in await repository.list_tracked()] == ["acme-crm", "beta", "zeta"]


async def test_recent_changes_are_marked(
    repository: PostgresCompetitorRepository, migrated_engine: Engine
):
    set_last_changed(migrated_engine, "changed-today", timedelta(hours=1))
    set_last_changed(migrated_engine, "changed-last-week", timedelta(days=7))
    set_last_changed(migrated_engine, "never-changed", None)

    tracked = await repository.list_tracked()

    assert {c.id: c.changed_recently for c in tracked} == {
        "changed-today": True,
        "changed-last-week": False,
        "never-changed": False,
    }


# --- snapshots ---


async def test_snapshots_are_newest_first(
    repository: PostgresCompetitorRepository, migrated_engine: Engine
):
    # Inserted out of time order: the order comes from fetched_at, not from the id.
    times = [START + timedelta(minutes=15), START, START + timedelta(minutes=30)]
    insert_snapshots(migrated_engine, "acme-crm", times)

    page = await repository.list_snapshots("acme-crm", None, None)

    assert [s.fetched_at for s in page] == sorted(times, reverse=True)


async def test_snapshots_use_the_default_page_size(
    repository: PostgresCompetitorRepository, migrated_engine: Engine
):
    insert_snapshots(migrated_engine, "acme-crm", [START + timedelta(minutes=m) for m in range(4)])

    assert len(await repository.list_snapshots("acme-crm", None, None)) == PAGE_SIZE


async def test_page_size_above_maximum_fails(repository: PostgresCompetitorRepository):
    await repository.add("acme-crm")

    with pytest.raises(InvalidPageSizeError):
        await repository.list_snapshots("acme-crm", MAX_PAGE_SIZE + 1, None)


async def test_snapshots_page_through_the_history(
    repository: PostgresCompetitorRepository, migrated_engine: Engine
):
    # Two snapshots share a time, so paging must also use the id.
    times = [START, START + timedelta(minutes=15), START + timedelta(minutes=15)]
    times += [START + timedelta(minutes=30), START + timedelta(minutes=45)]
    insert_snapshots(migrated_engine, "acme-crm", times)

    seen: list[int] = []
    before_id = None
    while page := await repository.list_snapshots("acme-crm", 2, before_id):
        seen += [s.id for s in page]
        before_id = page[-1].id

    assert seen == await all_snapshot_ids(repository, "acme-crm")
    assert len(seen) == len(times)


async def test_snapshots_of_other_competitors_are_left_out(
    repository: PostgresCompetitorRepository, migrated_engine: Engine
):
    [own_id] = insert_snapshots(migrated_engine, "acme-crm", [START])
    [other_id] = insert_snapshots(migrated_engine, "beta", [START + timedelta(minutes=15)])

    assert await all_snapshot_ids(repository, "acme-crm") == [own_id]
    # A cursor from another competitor gives an empty page, not that competitor's history.
    assert await repository.list_snapshots("acme-crm", None, other_id) == []


async def test_snapshot_columns_become_the_api_shape(
    repository: PostgresCompetitorRepository, migrated_engine: Engine
):
    insert_snapshots(migrated_engine, "acme-crm", [START])
    insert_snapshots(
        migrated_engine,
        "acme-crm",
        [START + timedelta(minutes=15)],
        outcome="failed",
        error={"kind": "timeout", "message": "Timed out after 10s", "after_seconds": 10},
        title=None,
        tagline=None,
        price_amount=None,
        price_currency=None,
        price_period=None,
        description=None,
        summary_status="poll_failed",
    )
    insert_snapshots(
        migrated_engine,
        "acme-crm",
        [START + timedelta(minutes=30)],
        changed=True,
        changes={"tagline": {"old": "Old", "new": "New"}},
        summary_status="llm_failed",
        summary_error={"kind": "http_status", "message": "The LLM answered 500", "status": 500},
    )

    llm_failed, poll_failed, ok = await repository.list_snapshots("acme-crm", None, None)

    assert (ok.price, ok.error) == ("$29/mo", None)
    assert (poll_failed.price, poll_failed.error) == (None, "Timed out after 10s")
    assert llm_failed.summary_error == "The LLM answered 500"


async def test_snapshot_prices_are_formatted(
    repository: PostgresCompetitorRepository, migrated_engine: Engine
):
    insert_snapshots(migrated_engine, "acme-crm", [START], price_unit="seat")
    insert_snapshots(
        migrated_engine,
        "acme-crm",
        [START + timedelta(minutes=15)],
        price_amount="0",
        price_currency=None,
        price_period=None,
    )

    free, per_seat = await repository.list_snapshots("acme-crm", None, None)

    assert (free.price, per_seat.price) == ("Free", "$29/seat/mo")
