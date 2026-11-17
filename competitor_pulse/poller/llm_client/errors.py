"""How a call to the LLM can fail.

Each error's structured_error has the fields of its record in competitor_pulse.errors, so the
summarizer can store it with summary_error_adapter.validate_python(err.structured_error).
"""

from competitor_pulse.errors import CompetitorPulseError


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
    """The connection to the LLM failed or was dropped."""

    def __init__(self, reason: str):
        super().__init__(f"Could not reach the LLM: {reason}", kind="connection")


class LlmHttpError(LlmError):
    """The LLM answered with an HTTP error status, like 500."""

    def __init__(self, status: int):
        super().__init__(f"The LLM answered with HTTP {status}", kind="http_status", status=status)


class LlmUnusableAnswerError(LlmError):
    """The LLM answered, but not with a summary we can show."""

    def __init__(self, reason: str):
        super().__init__(f"The LLM's answer was unusable: {reason}", kind="unusable")
