import asyncio
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest
from sqlalchemy import Engine, func, select
from sqlalchemy.dialects.postgresql import insert

from competitor_pulse.app.competitor_repository import PostgresCompetitorRepository
from competitor_pulse.configuration import ApiConfiguration
from competitor_pulse.database import Database
from competitor_pulse.errors import PollIncomplete, PollNotFound, PollTimeout
from competitor_pulse.models import ChangeView, Listing, PollResult
from competitor_pulse.poller.poll_repository import PostgresPollRepository
from competitor_pulse.tables import competitors, snapshots
from competitor_pulse.types import ListingField, PollOutcome, Price, PricePeriod

pytestmark = pytest.mark.anyio

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
def poll_repository(migrated_database: Database) -> PostgresPollRepository:
    return PostgresPollRepository(migrated_database.engine)


@pytest.fixture
def competitor_repository(migrated_database: Database) -> PostgresCompetitorRepository:
    # Adds and removes competitors and reads their snapshots, as the API does.
    return PostgresCompetitorRepository(migrated_database.engine, ApiConfiguration())


INTERVAL = timedelta(minutes=15)
LISTING = Listing(
    title="Lumen Docs",
    tagline="Docs your team will read",
    price=Price(amount=Decimal("12.00"), currency="USD", period=PricePeriod.MONTH, unit="seat"),
    description="Write, review and publish in one place.",
    missing_fields=[],
)


# LISTING as a snapshots row, for snapshots written without the repository.
LISTING_ROW: dict[str, Any] = {
    "outcome": "ok",
    "title": LISTING.title,
    "tagline": LISTING.tagline,
    "price_amount": "12.00",
    "price_currency": "USD",
    "price_period": "month",
    "price_unit": "seat",
    "description": LISTING.description,
    "changed": False,
}
NOT_FOUND = PollNotFound(message="The source does not list 'lumen-docs'")


def poll(outcome: PollOutcome = PollOutcome.OK, **fields: Any) -> PollResult:
    values: dict[str, Any] = {
        "fetched_at": START,
        "outcome": outcome,
        "error": None,
        "listing": LISTING,
    }
    return PollResult(**{**values, **fields})


def set_due(engine: Engine, competitor_id: str, ago: timedelta) -> None:
    with engine.begin() as connection:
        connection.execute(insert(competitors).values(id=competitor_id).on_conflict_do_nothing())
        connection.execute(
            competitors.update()
            .where(competitors.c.id == competitor_id)
            .values(next_poll_at=func.now() - ago)
        )


async def test_added_competitor_is_due_at_once(
    poll_repository: PostgresPollRepository, competitor_repository: PostgresCompetitorRepository
):
    await competitor_repository.add("acme-crm")

    assert await poll_repository.claim_due(10, INTERVAL) == ["acme-crm"]


async def test_most_overdue_competitors_are_claimed_first(
    poll_repository: PostgresPollRepository,
    competitor_repository: PostgresCompetitorRepository,
    migrated_engine: Engine,
):
    set_due(migrated_engine, "a", timedelta(minutes=3))
    set_due(migrated_engine, "b", timedelta(minutes=1))
    set_due(migrated_engine, "c", timedelta(minutes=2))
    set_due(migrated_engine, "not-yet", -timedelta(minutes=1))

    assert sorted(await poll_repository.claim_due(2, INTERVAL)) == ["a", "c"]
    assert await poll_repository.claim_due(2, INTERVAL) == ["b"]


async def test_claimed_competitor_is_due_again_after_the_interval(
    poll_repository: PostgresPollRepository,
    competitor_repository: PostgresCompetitorRepository,
    migrated_engine: Engine,
):
    await competitor_repository.add("acme-crm")

    await poll_repository.claim_due(10, INTERVAL)

    assert await poll_repository.claim_due(10, INTERVAL) == []
    with migrated_engine.connect() as connection:
        due_in: timedelta = connection.execute(
            select(competitors.c.next_poll_at - func.now())
        ).scalar_one()
    assert INTERVAL - timedelta(minutes=1) < due_in <= INTERVAL


async def test_removed_competitor_is_not_claimed(
    poll_repository: PostgresPollRepository, competitor_repository: PostgresCompetitorRepository
):
    await competitor_repository.add("acme-crm")
    await competitor_repository.remove("acme-crm")

    assert await poll_repository.claim_due(10, INTERVAL) == []


@pytest.mark.parametrize("make_due", ["requeue", "remove-and-add"])
async def test_competitor_can_be_made_due_again(
    poll_repository: PostgresPollRepository,
    competitor_repository: PostgresCompetitorRepository,
    make_due: str,
):
    await competitor_repository.add("acme-crm")
    await poll_repository.claim_due(10, INTERVAL)

    if make_due == "requeue":
        await poll_repository.requeue("acme-crm")
    else:
        await competitor_repository.remove("acme-crm")
        await competitor_repository.add("acme-crm")

    assert await poll_repository.claim_due(10, INTERVAL) == ["acme-crm"]


async def test_claim_skips_competitors_locked_by_another_transaction(
    poll_repository: PostgresPollRepository,
    competitor_repository: PostgresCompetitorRepository,
    migrated_engine: Engine,
):
    set_due(migrated_engine, "locked", timedelta(minutes=2))
    set_due(migrated_engine, "free", timedelta(minutes=1))

    with migrated_engine.begin() as other:
        other.execute(select(competitors).where(competitors.c.id == "locked").with_for_update())

        assert await poll_repository.claim_due(10, INTERVAL) == ["free"]


async def test_polls_are_stored_as_snapshots(
    poll_repository: PostgresPollRepository, competitor_repository: PostgresCompetitorRepository
):
    await competitor_repository.add("lumen-docs")
    incomplete = LISTING.model_copy(update={"price": None, "missing_fields": [ListingField.PRICE]})
    timeout = PollTimeout(message="The source did not answer within 10s", after_seconds=10)
    missing = PollIncomplete(message="The source left out price", fields=[ListingField.PRICE])

    await poll_repository.save_poll("lumen-docs", poll())
    await poll_repository.save_poll(
        "lumen-docs",
        poll(fetched_at=START + INTERVAL, outcome=PollOutcome.FAILED, error=timeout, listing=None),
    )
    await poll_repository.save_poll(
        "lumen-docs",
        poll(
            fetched_at=START + 2 * INTERVAL,
            outcome=PollOutcome.INCOMPLETE,
            error=missing,
            listing=incomplete,
        ),
    )

    newest, failed, first = await competitor_repository.list_snapshots("lumen-docs", None, None)
    assert (first.outcome, first.price, first.summary_status) == ("ok", "$12/seat/mo", "baseline")
    assert (failed.outcome, failed.title, failed.error) == ("failed", None, timeout.message)
    assert (newest.outcome, newest.price, newest.error) == ("incomplete", None, missing.message)
    assert (newest.title, newest.summary_status) == ("Lumen Docs", "no_change")


async def test_poll_of_removed_competitor_is_dropped(
    poll_repository: PostgresPollRepository, competitor_repository: PostgresCompetitorRepository
):
    await competitor_repository.add("acme-crm")
    await competitor_repository.remove("acme-crm")

    assert await poll_repository.save_poll("acme-crm", poll()) is False

    await competitor_repository.add("acme-crm")
    assert await competitor_repository.list_snapshots("acme-crm", None, None) == []


async def test_save_waits_for_a_concurrent_save_and_sees_its_snapshot(
    poll_repository: PostgresPollRepository,
    competitor_repository: PostgresCompetitorRepository,
    migrated_database: Database,
):
    await competitor_repository.add("acme-crm")

    # Another save of the same competitor is half-way: row locked, first listing inserted and
    # remembered.
    async with migrated_database.engine.begin() as other_save:
        await other_save.execute(
            competitors.update()
            .where(competitors.c.id == "acme-crm")
            .values(known_listing=LISTING.model_dump(mode="json", exclude={"missing_fields"}))
        )
        await other_save.execute(
            snapshots.insert().values(
                {
                    **LISTING_ROW,
                    "competitor_id": "acme-crm",
                    "fetched_at": START,
                    "summary_status": "baseline",
                }
            )
        )
        saving = asyncio.create_task(
            poll_repository.save_poll("acme-crm", poll(fetched_at=START + timedelta(seconds=1)))
        )
        await asyncio.sleep(0.3)
        assert not saving.done()

    await saving
    statuses = [
        s.summary_status for s in await competitor_repository.list_snapshots("acme-crm", None, None)
    ]
    assert statuses == ["no_change", "baseline"]


async def snapshots_of(competitor_repository: PostgresCompetitorRepository, competitor_id: str):
    """The competitor's snapshots, oldest first."""
    return list(reversed(await competitor_repository.list_snapshots(competitor_id, None, None)))


async def test_a_change_is_stored_with_what_changed(
    poll_repository: PostgresPollRepository,
    competitor_repository: PostgresCompetitorRepository,
    migrated_engine: Engine,
):
    await competitor_repository.add("lumen-docs")
    cheaper_price = Price(
        amount=Decimal("10.00"), currency="USD", period=PricePeriod.MONTH, unit="seat"
    )
    cheaper = LISTING.model_copy(update={"price": cheaper_price})

    await poll_repository.save_poll("lumen-docs", poll())
    await poll_repository.save_poll(
        "lumen-docs", poll(fetched_at=START + INTERVAL, listing=cheaper)
    )

    baseline, change = await snapshots_of(competitor_repository, "lumen-docs")
    assert (baseline.changed, baseline.summary_status) == (False, "baseline")
    assert (change.changed, change.summary_status, change.price) == (True, "pending", "$10/seat/mo")
    with migrated_engine.connect() as connection:
        stored = connection.execute(select(snapshots.c.changes).where(snapshots.c.id == change.id))
        assert stored.scalar_one() == {
            "price": {
                "old": {"amount": "12.00", "currency": "USD", "period": "month", "unit": "seat"},
                "new": {"amount": "10.00", "currency": "USD", "period": "month", "unit": "seat"},
            }
        }
    [competitor] = await competitor_repository.list_tracked()
    assert competitor.last_changed_at == START + INTERVAL


async def test_a_failed_poll_in_between_does_not_break_the_comparison(
    poll_repository: PostgresPollRepository,
    competitor_repository: PostgresCompetitorRepository,
):
    await competitor_repository.add("lumen-docs")
    timeout = PollTimeout(message="The source did not answer within 10s", after_seconds=10)

    await poll_repository.save_poll("lumen-docs", poll())
    await poll_repository.save_poll(
        "lumen-docs",
        poll(fetched_at=START + INTERVAL, outcome=PollOutcome.FAILED, error=timeout, listing=None),
    )
    await poll_repository.save_poll("lumen-docs", poll(fetched_at=START + 2 * INTERVAL))

    statuses = [s.summary_status for s in await snapshots_of(competitor_repository, "lumen-docs")]
    assert statuses == ["baseline", "poll_failed", "no_change"]
    [competitor] = await competitor_repository.list_tracked()
    assert competitor.last_changed_at is None


async def test_a_change_after_an_incomplete_poll_is_compared_with_the_last_value_read(
    poll_repository: PostgresPollRepository,
    competitor_repository: PostgresCompetitorRepository,
):
    await competitor_repository.add("lumen-docs")
    incomplete = LISTING.model_copy(update={"price": None, "missing_fields": [ListingField.PRICE]})
    missing = PollIncomplete(message="The source left out price", fields=[ListingField.PRICE])
    cheaper_price = Price(
        amount=Decimal("10.00"), currency="USD", period=PricePeriod.MONTH, unit="seat"
    )

    await poll_repository.save_poll("lumen-docs", poll())
    await poll_repository.save_poll(
        "lumen-docs",
        poll(
            fetched_at=START + INTERVAL,
            outcome=PollOutcome.INCOMPLETE,
            error=missing,
            listing=incomplete,
        ),
    )
    await poll_repository.save_poll(
        "lumen-docs",
        poll(
            fetched_at=START + 2 * INTERVAL,
            listing=LISTING.model_copy(update={"price": cheaper_price}),
        ),
    )

    history = [
        (s.summary_status, s.changes)
        for s in await snapshots_of(competitor_repository, "lumen-docs")
    ]
    assert history == [
        ("baseline", None),
        ("no_change", None),
        ("pending", {"price": ChangeView(old="$12/seat/mo", new="$10/seat/mo")}),
    ]


async def test_disappearing_and_coming_back_are_changes_with_fixed_summaries(
    poll_repository: PostgresPollRepository,
    competitor_repository: PostgresCompetitorRepository,
):
    await competitor_repository.add("lumen-docs")
    not_found: dict[str, Any] = {
        "outcome": PollOutcome.NOT_FOUND,
        "error": NOT_FOUND,
        "listing": None,
    }

    await poll_repository.save_poll("lumen-docs", poll())
    await poll_repository.save_poll("lumen-docs", poll(fetched_at=START + INTERVAL, **not_found))
    await poll_repository.save_poll(
        "lumen-docs", poll(fetched_at=START + 2 * INTERVAL, **not_found)
    )
    await poll_repository.save_poll("lumen-docs", poll(fetched_at=START + 3 * INTERVAL))

    history = [
        (s.outcome, s.changed, s.summary_status, s.summary)
        for s in await snapshots_of(competitor_repository, "lumen-docs")
    ]
    assert history == [
        ("ok", False, "baseline", None),
        ("not_found", True, "ready", "The listing is no longer on the source."),
        ("not_found", False, "poll_failed", None),
        ("ok", True, "ready", "The listing is back, unchanged."),
    ]
    [competitor] = await competitor_repository.list_tracked()
    assert competitor.last_changed_at == START + 3 * INTERVAL
