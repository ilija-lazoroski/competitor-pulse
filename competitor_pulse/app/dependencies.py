from competitor_pulse.database import Database

# Shared between requests: set in setup(), cleaned up in teardown(). Tests replace
# them with app.dependency_overrides.
_database: Database | None = None


def database() -> Database:
    if _database is None:
        raise RuntimeError("The database is not initialised; setup() has not run")
    return _database
