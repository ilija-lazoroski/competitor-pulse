from datetime import timedelta


class SpyRetentionRepository:
    """A spy: deletes from given counts, can fail a number of rounds, and records each batch."""

    def __init__(self, old_snapshots: int = 0, removed_competitors: int = 0, failures: int = 0):
        self.old_snapshots = old_snapshots
        self.removed_competitors = removed_competitors
        self.failures = failures
        self.deleted_batches: list[int] = []

    async def delete_snapshots_older_than(self, retention: timedelta, limit: int) -> int:
        if self.failures:
            self.failures -= 1
            raise ConnectionError("database is down")
        deleted = min(limit, self.old_snapshots)
        self.old_snapshots -= deleted
        self.deleted_batches.append(deleted)
        return deleted

    async def delete_removed_competitors_older_than(self, retention: timedelta) -> int:
        deleted, self.removed_competitors = self.removed_competitors, 0
        return deleted
