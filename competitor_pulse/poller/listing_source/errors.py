"""How fetching a listing from the source can fail.

Each error's structured_error has the fields of its record in competitor_pulse.errors, so the
poller can store it with poll_error_adapter.validate_python(err.structured_error).
"""

from competitor_pulse.errors import CompetitorPulseError


class SourceError(CompetitorPulseError):
    """Base class for the ways fetching a listing from the source can fail."""


class ListingNotFoundError(SourceError):
    """The source does not know the competitor, or does not list it at the moment."""

    def __init__(self, competitor_id: str):
        super().__init__(f"The source does not list {competitor_id!r}", kind="not_found")


class SourceTimeoutError(SourceError):
    """The source did not answer in time."""

    def __init__(self, after_seconds: float):
        super().__init__(
            f"The source did not answer within {after_seconds:g}s",
            kind="timeout",
            after_seconds=after_seconds,
        )


class SourceConnectionError(SourceError):
    """The connection to the source failed or was dropped."""

    def __init__(self, reason: str):
        super().__init__(f"Could not reach the source: {reason}", kind="connection")


class SourceRateLimitedError(SourceError):
    """The source refused the request because of its global rate limit."""

    def __init__(self, retry_after_seconds: float | None):
        super().__init__(
            "The source is rate limiting requests",
            kind="rate_limited",
            retry_after_seconds=retry_after_seconds,
        )


class SourceHttpError(SourceError):
    """The source answered with an unexpected HTTP status, like 500 or 502."""

    def __init__(self, status: int):
        super().__init__(
            f"The source answered with HTTP {status}", kind="http_status", status=status
        )


class SourceInvalidBodyError(SourceError):
    """The source answered 200, but not with a JSON object."""

    def __init__(self, reason: str):
        super().__init__(f"The source sent an unreadable listing: {reason}", kind="invalid_body")
