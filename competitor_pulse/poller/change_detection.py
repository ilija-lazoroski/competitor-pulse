"""Decides whether a poll changed something that matters to a product manager.

The parser already removed the source's noise, so any difference left in a field is a change.
Fields a poll could not read are unknown, not removed, so they never count as a change, and
the next poll is compared with the last value that was read.
"""

from typing import Final

from service_kit import ServiceKitBaseModel

from competitor_pulse.models import Listing, ListingValues, PollResult
from competitor_pulse.types import Changes, FieldChange, ListingField, PollOutcome, SummaryStatus

DELISTED_SUMMARY: Final[str] = "The listing is no longer on the source."
RELISTED_UNCHANGED_SUMMARY: Final[str] = "The listing is back, unchanged."


class ChangeDecision(ServiceKitBaseModel):
    """Whether a poll changed something, what changed, and what happens to its summary."""

    changed: bool
    changes: Changes | None
    summary: str | None
    summary_status: SummaryStatus


def decide(
    result: PollResult, previous_listing: ListingValues | None, previously_delisted: bool
) -> ChangeDecision:
    """Compares a poll with the competitor's state before it.

    A change in the listing waits for the LLM's summary; a competitor that disappears from the
    source, or comes back unchanged, gets a fixed summary instead.

    :param result: What the poll found
    :param previous_listing: The last value read for each field before this poll (see
                             remember()); None if no poll ever read one
    :param previously_delisted: True if the source did not list the competitor at its latest
                                earlier poll that got an answer
    :returns: The decision to store with the poll's snapshot
    """
    if result.outcome == PollOutcome.FAILED:
        return _unchanged(SummaryStatus.POLL_FAILED)

    if result.outcome == PollOutcome.NOT_FOUND:
        if previous_listing is None or previously_delisted:
            return _unchanged(SummaryStatus.POLL_FAILED)
        return ChangeDecision(
            changed=True,
            changes=compare(previous_listing, None),
            summary=DELISTED_SUMMARY,
            summary_status=SummaryStatus.READY,
        )

    if previous_listing is None:
        return _unchanged(SummaryStatus.BASELINE)

    changes = compare(previous_listing, result.listing)
    if changes:
        return ChangeDecision(
            changed=True, changes=changes, summary=None, summary_status=SummaryStatus.PENDING
        )
    if previously_delisted:
        return ChangeDecision(
            changed=True,
            changes={},
            summary=RELISTED_UNCHANGED_SUMMARY,
            summary_status=SummaryStatus.READY,
        )
    return _unchanged(SummaryStatus.NO_CHANGE)


def remember(known: ListingValues | None, listing: Listing) -> ListingValues | None:
    """Updates the last known value of each field with what a poll read.

    :param known: The last known values before the poll; None if no poll ever read one
    :param listing: The listing the poll read
    :returns: The poll's value for each field it read, the known value for the others; None
              if no value is known yet
    """
    values = {
        field.value: (
            getattr(listing, field)
            if getattr(listing, field) is not None
            else getattr(known, field, None)
        )
        for field in ListingField
    }
    if all(value is None for value in values.values()):
        return None
    return ListingValues(**values)


def compare(previous: ListingValues, current: Listing | None) -> Changes:
    """Lists the fields whose value differs between two listings.

    :param previous: The earlier listing, or the last known value of each field
    :param current: The new listing; None if the competitor is no longer listed, which removes
                    every field the earlier listing had
    :returns: The changed fields with their old and new values; empty if nothing changed
    """
    changes: Changes = {}
    for field in ListingField:
        old = getattr(previous, field)
        if current is None:
            if old is not None:
                changes[field] = FieldChange(old=old, new=None)
            continue
        new = getattr(current, field)
        if old is not None and new is not None and old != new:
            changes[field] = FieldChange(old=old, new=new)
    return changes


def _unchanged(summary_status: SummaryStatus) -> ChangeDecision:
    """A decision that nothing changed.

    :param summary_status: Why the snapshot has no summary
    :returns: The decision
    """
    return ChangeDecision(changed=False, changes=None, summary=None, summary_status=summary_status)
