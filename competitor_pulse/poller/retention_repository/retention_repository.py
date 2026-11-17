from datetime import timedelta
from typing import Protocol


class RetentionRepository(Protocol):
    """Deletes history that is older than the retention period."""

    async def delete_snapshots_older_than(self, retention: timedelta, limit: int) -> int:
        """Deletes up to `limit` snapshots fetched more than `retention` ago, in one transaction.

        :param retention: How long snapshots are kept
        :param limit: The most snapshots to delete
        :returns: How many snapshots were deleted; fewer than `limit` means none are left
        """
        ...

    async def delete_removed_competitors_older_than(self, retention: timedelta) -> int:
        """Deletes competitors removed more than `retention` ago that have no snapshots left.

        A competitor that was added again meanwhile is tracked, so it is never deleted.

        :param retention: How long a removed competitor is kept
        :returns: How many competitors were deleted
        """
        ...
