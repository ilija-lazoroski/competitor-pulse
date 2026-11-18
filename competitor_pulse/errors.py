"""The application's exceptions, and the records of failures stored with a snapshot.

The two are different things:

- CompetitorPulseError is the base of the exceptions the application raises. The source and
  LLM clients raise subclasses of it (service-kit StructuredErrors), which live only while the
  poller handles them.
- FailureRecord is the base of the records stored in snapshots.error and summary_error and
  returned by the API. They are Pydantic models, not exceptions: data with a schema, which the
  database and the API can use and an exception cannot.

An exception's `structured_error` has the fields of its record, so the poller turns one into
the other with `poll_failure_adapter.validate_python(err.structured_error)`.
"""

from typing import Annotated, Final, Literal

from pydantic import Field, TypeAdapter
from service_kit import ServiceKitBaseModel, StructuredError

from competitor_pulse.types import ListingField


class CompetitorPulseError(StructuredError):
    """Base class for all exceptions the application raises."""


class FailureRecord(ServiceKitBaseModel):
    """A failure stored with a snapshot and returned by the API; not an exception.

    `kind` in the subclasses tells which one.
    """

    message: str = Field(description="Readable explanation, shown to the user")


# Stored in snapshots.error: why a poll did not return a complete listing.


class PollNotFound(FailureRecord):
    kind: Literal["not_found"] = "not_found"


class PollTimeout(FailureRecord):
    kind: Literal["timeout"] = "timeout"
    after_seconds: float


class PollConnectionFailed(FailureRecord):
    kind: Literal["connection"] = "connection"


class PollHTTPStatus(FailureRecord):
    kind: Literal["http_status"] = "http_status"
    status: int


class PollRateLimited(FailureRecord):
    kind: Literal["rate_limited"] = "rate_limited"
    retry_after_seconds: float | None


class PollInvalidBody(FailureRecord):
    kind: Literal["invalid_body"] = "invalid_body"


class PollIncomplete(FailureRecord):
    kind: Literal["incomplete"] = "incomplete"
    fields: list[ListingField]


PollFailure = Annotated[
    PollNotFound
    | PollTimeout
    | PollConnectionFailed
    | PollHTTPStatus
    | PollRateLimited
    | PollInvalidBody
    | PollIncomplete,
    Field(discriminator="kind"),
]
poll_failure_adapter: Final[TypeAdapter[PollFailure]] = TypeAdapter(PollFailure)


# Stored in snapshots.summary_error: why the LLM did not give a summary.


class SummaryTimeout(FailureRecord):
    kind: Literal["timeout"] = "timeout"
    after_seconds: float


class SummaryConnectionFailed(FailureRecord):
    kind: Literal["connection"] = "connection"


class SummaryHTTPStatus(FailureRecord):
    kind: Literal["http_status"] = "http_status"
    status: int


class SummaryUnusableAnswer(FailureRecord):
    kind: Literal["unusable"] = "unusable"


SummaryFailure = Annotated[
    SummaryTimeout | SummaryConnectionFailed | SummaryHTTPStatus | SummaryUnusableAnswer,
    Field(discriminator="kind"),
]
summary_failure_adapter: Final[TypeAdapter[SummaryFailure]] = TypeAdapter(SummaryFailure)
