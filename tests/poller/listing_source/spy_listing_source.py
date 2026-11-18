from competitor_pulse.models import Listing
from competitor_pulse.types import CompetitorID


class SpyListingSource:
    """A spy: answers each competitor with a given listing or error, and records each fetch."""

    def __init__(self, answers: dict[str, Listing | Exception]):
        self._answers = answers
        self.fetched: list[str] = []

    async def fetch(self, competitor_id: CompetitorID) -> Listing:
        self.fetched.append(competitor_id)
        answer = self._answers[competitor_id]
        if isinstance(answer, Exception):
            raise answer
        return answer
