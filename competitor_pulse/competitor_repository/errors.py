"""How the competitor repository's operations can fail."""

from competitor_pulse.errors import CompetitorPulseError


class CompetitorNotTrackedError(CompetitorPulseError):
    """The competitor is not tracked: it was never added, or it was removed."""

    def __init__(self, competitor_id: str):
        super().__init__(
            f"Competitor {competitor_id!r} is not tracked", competitor_id=competitor_id
        )


class CompetitorAlreadyTrackedError(CompetitorPulseError):
    """The competitor is tracked already, so it cannot be added again."""

    def __init__(self, competitor_id: str):
        super().__init__(
            f"Competitor {competitor_id!r} is already tracked", competitor_id=competitor_id
        )


class InvalidPageSizeError(CompetitorPulseError):
    """The requested page size is above the configured maximum."""

    def __init__(self, limit: int, max_page_size: int):
        super().__init__(
            f"limit must not be larger than {max_page_size}",
            limit=limit,
            max_page_size=max_page_size,
        )
