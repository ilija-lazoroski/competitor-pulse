"""How a call to the LLM can fail.

Each error's structured_error has the fields of its record in competitor_pulse.errors, so the
summarizer can store it with summary_error_adapter.validate_python(err.structured_error).
"""

from http import HTTPStatus
from typing import Final

from competitor_pulse.errors import CompetitorPulseError

# Besides server errors (5xx), the statuses where the same request can succeed later.
_RETRYABLE_STATUSES: Final = frozenset({HTTPStatus.REQUEST_TIMEOUT, HTTPStatus.TOO_MANY_REQUESTS})


class LlmError(CompetitorPulseError):
    """Base class for the ways a call to the LLM can fail."""


class LlmTimeoutError(LlmError):
    """The LLM did not answer in time."""

    def __init__(self, after_seconds: float):
        super().__init__(
            f"The LLM did not answer within {after_seconds:g}s",
            kind="timeout",
            after_seconds=after_seconds,
        )


class LlmConnectionError(LlmError):
    """The request to the LLM failed without an answer: connection, protocol or decoding."""

    def __init__(self, reason: str):
        super().__init__(f"Could not reach the LLM: {reason}", kind="connection")


class LlmHttpError(LlmError):
    """The LLM answered with an HTTP error status, like 500."""

    def __init__(self, status: int):
        super().__init__(f"The LLM answered with HTTP {status}", kind="http_status", status=status)
        # Not part of structured_error: it is not stored, it only decides about another attempt.
        self.retryable = status >= HTTPStatus.INTERNAL_SERVER_ERROR or status in _RETRYABLE_STATUSES


class LlmUnusableAnswerError(LlmError):
    """The LLM answered, but not with a summary we can show."""

    def __init__(self, reason: str):
        super().__init__(f"The LLM's answer was unusable: {reason}", kind="unusable")
