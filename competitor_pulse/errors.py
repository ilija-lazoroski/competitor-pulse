"""The application's errors, and the error records stored with a snapshot.

Each record has the shape of a service-kit StructuredError's `structured_error` (a `message`
plus the error's fields), so the exceptions the source and LLM clients raise can be stored
with `poll_error_adapter.validate_python(err.structured_error)`.
"""

from typing import Annotated, Final, Literal

from pydantic import Field, TypeAdapter
from service_kit import ServiceKitBaseModel, StructuredError

from competitor_pulse.types import ListingField


class CompetitorPulseError(StructuredError):
    """Base class for all errors in the application."""


class ErrorRecord(ServiceKitBaseModel):
    """An error stored with a snapshot; `kind` in the subclasses tells which one."""

    message: str = Field(description="Readable explanation, shown to the user")


# Stored in snapshots.error: why a poll did not return a complete listing.


class PollNotFound(ErrorRecord):
    kind: Literal["not_found"] = "not_found"


class PollTimeout(ErrorRecord):
    kind: Literal["timeout"] = "timeout"
    after_seconds: float


class PollConnectionError(ErrorRecord):
    kind: Literal["connection"] = "connection"


class PollHttpError(ErrorRecord):
    kind: Literal["http_status"] = "http_status"
    status: int


class PollRateLimited(ErrorRecord):
    kind: Literal["rate_limited"] = "rate_limited"
    retry_after_seconds: float | None


class PollInvalidBody(ErrorRecord):
    kind: Literal["invalid_body"] = "invalid_body"


class PollIncomplete(ErrorRecord):
    kind: Literal["incomplete"] = "incomplete"
    fields: list[ListingField]


PollError = Annotated[
    PollNotFound
    | PollTimeout
    | PollConnectionError
    | PollHttpError
    | PollRateLimited
    | PollInvalidBody
    | PollIncomplete,
    Field(discriminator="kind"),
]
poll_error_adapter: Final = TypeAdapter(PollError)


# Stored in snapshots.summary_error: why the LLM did not give a summary.


class LlmTimeout(ErrorRecord):
    kind: Literal["timeout"] = "timeout"
    after_seconds: float


class LlmConnectionError(ErrorRecord):
    kind: Literal["connection"] = "connection"


class LlmHttpError(ErrorRecord):
    kind: Literal["http_status"] = "http_status"
    status: int


class LlmUnusableAnswer(ErrorRecord):
    kind: Literal["unusable"] = "unusable"


SummaryError = Annotated[
    LlmTimeout | LlmConnectionError | LlmHttpError | LlmUnusableAnswer,
    Field(discriminator="kind"),
]
summary_error_adapter: Final = TypeAdapter(SummaryError)
