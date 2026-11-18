import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import Engine, func, select, text
from sqlalchemy.dialects.postgresql import insert

from competitor_pulse.database import Database
from competitor_pulse.errors import SummaryHTTPStatus, SummaryUnusableAnswer
from competitor_pulse.poller.summary_repository import PostgresSummaryRepository
from competitor_pulse.tables import competitors, llm_usage, snapshots
from competitor_pulse.types import FieldChange, ListingField

pytestmark = pytest.mark.anyio

START = datetime(2026, 9, 10, 12, tzinfo=UTC)
CHANGES = {"title": {"old": "Acme CRM", "new": "Acme CRM Pro"}}


@pytest.fixture
def repository(migrated_database: Database) -> PostgresSummaryRepository:
    return PostgresSummaryRepository(migrated_database.engine)


def add_snapshot(engine: Engine, minutes: int, summary_status: str = "pending") -> int:
    """Adds a changed snapshot of acme-crm, `minutes` after START, and returns its id."""
    row: dict[str, Any] = {
        "competitor_id": "acme-crm",
        "fetched_at": START + timedelta(minutes=minutes),
        "outcome": "ok",
        "title": "Acme CRM Pro",
        "changed": True,
        "changes": CHANGES,
        "summary_status": summary_status,
    }
    with engine.begin() as connection:
        connection.execute(insert(competitors).values(id="acme-crm").on_conflict_do_nothing())
        return connection.execute(
            snapshots.insert().values(row).returning(snapshots.c.id)
        ).scalar_one()


def statuses(engine: Engine) -> dict[int, tuple[str, Any, Any]]:
    with engine.connect() as connection:
        rows = connection.execute(
            select(
                snapshots.c.id,
                snapshots.c.summary_status,
                snapshots.c.summary,
                snapshots.c.summary_error,
            )
        )
        return {row.id: (row.summary_status, row.summary, row.summary_error) for row in rows}


# --- the daily cap ---


async def test_concurrent_reservations_never_go_past_the_cap(
    repository: PostgresSummaryRepository,
):
    granted = await asyncio.gather(*(repository.reserve_llm_call(3) for _ in range(10)))

    assert granted.count(True) == 3


async def test_cap_of_zero_allows_no_call(repository: PostgresSummaryRepository):
    assert await repository.reserve_llm_call(0) is False


async def test_the_cap_starts_again_each_utc_day(
    repository: PostgresSummaryRepository, migrated_engine: Engine
):
    # Yesterday's calls are used up.
    with migrated_engine.begin() as connection:
        connection.execute(
            text("INSERT INTO llm_usage VALUES ((now() AT TIME ZONE 'UTC')::date - 1, 5)")
        )

    assert await repository.reserve_llm_call(5) is True
    with migrated_engine.connect() as connection:
        assert connection.execute(select(func.count()).select_from(llm_usage)).scalar_one() == 2


# --- pending changes ---


async def test_pending_changes_are_listed_newest_first(
    repository: PostgresSummaryRepository, migrated_engine: Engine
):
    old = add_snapshot(migrated_engine, 0)
    new = add_snapshot(migrated_engine, 30)
    middle = add_snapshot(migrated_engine, 15)
    add_snapshot(migrated_engine, 45, summary_status="cap_reached")

    pending = await repository.pending(limit=10, exclude=[])

    assert [p.snapshot_id for p in pending] == [new, middle, old]
    assert pending[0].changes == {
        ListingField.TITLE: FieldChange(old="Acme CRM", new="Acme CRM Pro")
    }


async def test_pending_leaves_out_excluded_changes_and_stops_at_the_limit(
    repository: PostgresSummaryRepository, migrated_engine: Engine
):
    ids = [add_snapshot(migrated_engine, minutes) for minutes in range(4)]

    pending = await repository.pending(limit=2, exclude=[ids[3]])

    assert [p.snapshot_id for p in pending] == [ids[2], ids[1]]


# --- storing the outcome ---


async def test_summary_is_stored(repository: PostgresSummaryRepository, migrated_engine: Engine):
    snapshot_id = add_snapshot(migrated_engine, 0)

    await repository.save_summary(snapshot_id, "The title is now Acme CRM Pro.")

    assert statuses(migrated_engine)[snapshot_id] == (
        "ready",
        "The title is now Acme CRM Pro.",
        None,
    )


@pytest.mark.parametrize(
    ("error", "unusable", "status"),
    [
        (
            SummaryHTTPStatus(message="The LLM answered with HTTP 500", status=500),
            False,
            "llm_failed",
        ),
        (SummaryUnusableAnswer(message="The answer was empty"), True, "llm_unusable"),
    ],
)
async def test_failure_is_stored_with_its_reason(
    repository: PostgresSummaryRepository,
    migrated_engine: Engine,
    error: Any,
    unusable: bool,
    status: str,
):
    snapshot_id = add_snapshot(migrated_engine, 0)

    await repository.save_failure(snapshot_id, error, unusable)

    assert statuses(migrated_engine)[snapshot_id] == (status, None, error.model_dump(mode="json"))


async def test_only_pending_changes_are_updated(
    repository: PostgresSummaryRepository, migrated_engine: Engine
):
    snapshot_id = add_snapshot(migrated_engine, 0, summary_status="cap_reached")

    await repository.save_summary(snapshot_id, "Too late.")

    assert statuses(migrated_engine)[snapshot_id] == ("cap_reached", None, None)


async def test_cap_reached_marks_every_pending_change_except_those_in_flight(
    repository: PostgresSummaryRepository, migrated_engine: Engine
):
    in_flight = add_snapshot(migrated_engine, 0)
    waiting = [add_snapshot(migrated_engine, minutes) for minutes in (1, 2)]

    marked = await repository.mark_cap_reached(exclude=[in_flight])

    assert marked == 2
    current = statuses(migrated_engine)
    assert current[in_flight][0] == "pending"
    assert [current[id_][0] for id_ in waiting] == ["cap_reached", "cap_reached"]
