from typing import Annotated

from fastapi import Depends

from competitor_pulse.competitor_repository import (
    CompetitorRepository,
    PostgresCompetitorRepository,
)
from competitor_pulse.configuration import ApiConfiguration
from competitor_pulse.database import Database

# Shared between requests: set in setup(), cleaned up in teardown(). Tests replace
# them with app.dependency_overrides.
_database: Database | None = None
_api_configuration: ApiConfiguration | None = None


def database() -> Database:
    if _database is None:
        raise RuntimeError("The database is not initialised; setup() has not run")
    return _database


def api_configuration() -> ApiConfiguration:
    if _api_configuration is None:
        raise RuntimeError("The configuration is not loaded; setup() has not run")
    return _api_configuration


def competitor_repository(
    db: Annotated[Database, Depends(database)],
    config: Annotated[ApiConfiguration, Depends(api_configuration)],
) -> CompetitorRepository:
    return PostgresCompetitorRepository(db.engine, config)
