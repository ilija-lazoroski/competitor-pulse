from typing import Any

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from sqlalchemy import Engine, inspect, text
from sqlalchemy.exc import IntegrityError

from competitor_pulse.tables import competitors, metadata, snapshots

COMPETITOR_ID = "acme-crm"
OK_SNAPSHOT: dict[str, Any] = {
    "competitor_id": COMPETITOR_ID,
    "fetched_at": "2026-09-10T12:00:00Z",
    "outcome": "ok",
    "error": None,
    "title": "Acme CRM",
    "tagline": "Simple CRM for small teams",
    "price_amount": "29.00",
    "price_currency": "USD",
    "price_period": "month",
    "description": "Track leads and deals in one place.",
    "changed": False,
    "changes": None,
    "summary": None,
    "summary_status": "no_change",
    "summary_error": None,
}


def insert_snapshot(engine: Engine, **overrides: Any) -> None:
    with engine.begin() as connection:
        connection.execute(competitors.insert().values(id=COMPETITOR_ID))
        connection.execute(snapshots.insert().values(**{**OK_SNAPSHOT, **overrides}))


def test_migrations_match_the_tables(migrated_engine: Engine):
    with migrated_engine.connect() as connection:
        context = MigrationContext.configure(connection, opts={"compare_type": True})
        differences = compare_metadata(context, metadata)

    assert differences == []


def test_downgrade_removes_everything(alembic_config: Config, migrated_engine: Engine):
    command.downgrade(alembic_config, "base")

    with migrated_engine.connect() as connection:
        assert set(inspect(connection).get_table_names()) == {"alembic_version"}
        enums = connection.execute(text("SELECT typname FROM pg_type WHERE typtype = 'e'"))
        assert enums.scalars().all() == []


def test_upgrade_after_downgrade_works(alembic_config: Config, migrated_engine: Engine):
    command.downgrade(alembic_config, "base")
    command.upgrade(alembic_config, "head")

    insert_snapshot(migrated_engine)


@pytest.mark.parametrize(
    "overrides",
    [
        {},
        # A failed poll: no listing, an error, no summary.
        {
            "outcome": "failed",
            "error": {"kind": "timeout", "message": "Timed out", "after_seconds": 10},
            "title": None,
            "tagline": None,
            "price_amount": None,
            "price_currency": None,
            "price_period": None,
            "description": None,
            "summary_status": "poll_failed",
        },
        # A change with its summary.
        {
            "changed": True,
            "changes": {"tagline": {"old": "Old", "new": "Simple CRM for small teams"}},
            "summary": "The tagline changed.",
            "summary_status": "ready",
        },
        # A change the LLM could not summarise.
        {
            "changed": True,
            "changes": {"tagline": {"old": "Old", "new": "New"}},
            "summary_status": "llm_failed",
            "summary_error": {"kind": "http_status", "message": "Server error", "status": 500},
        },
    ],
)
def test_valid_snapshots_are_stored(migrated_engine: Engine, overrides: dict[str, Any]):
    insert_snapshot(migrated_engine, **overrides)


@pytest.mark.parametrize(
    ("overrides", "constraint"),
    [
        (
            {"error": {"kind": "timeout", "message": "Timed out", "after_seconds": 1}},
            "error_iff_not_ok",
        ),
        ({"outcome": "failed"}, "error_iff_not_ok"),
        ({"price_currency": None}, "price_all_or_nothing"),
        ({"price_period": None}, "price_all_or_nothing"),
        ({"price_amount": "-1"}, "price_amount_not_negative"),
        ({"price_currency": "usd"}, "price_currency_iso_4217"),
        ({"changed": True}, "changes_iff_changed"),
        ({"changes": {"title": {"old": "a", "new": "b"}}}, "changes_iff_changed"),
        ({"summary_status": "ready"}, "summary_iff_ready"),
        ({"summary": "A summary for nothing."}, "summary_iff_ready"),
        ({"summary_status": "llm_unusable"}, "summary_error_iff_llm_error"),
        (
            {"summary_error": {"kind": "unusable", "message": "Empty answer"}},
            "summary_error_iff_llm_error",
        ),
    ],
)
def test_inconsistent_snapshots_are_rejected(
    migrated_engine: Engine, overrides: dict[str, Any], constraint: str
):
    with pytest.raises(IntegrityError, match=f"ck_snapshots_{constraint}"):
        insert_snapshot(migrated_engine, **overrides)


def test_snapshot_needs_a_known_competitor(migrated_engine: Engine):
    with pytest.raises(IntegrityError, match="fk_snapshots_competitor_id_competitors"):
        with migrated_engine.begin() as connection:
            connection.execute(snapshots.insert().values(**OK_SNAPSHOT))


def test_deleting_a_competitor_deletes_its_snapshots(migrated_engine: Engine):
    insert_snapshot(migrated_engine)

    with migrated_engine.begin() as connection:
        connection.execute(competitors.delete().where(competitors.c.id == COMPETITOR_ID))
        count = connection.execute(text("SELECT count(*) FROM snapshots"))
        remaining: int = count.scalar_one()

    assert remaining == 0
