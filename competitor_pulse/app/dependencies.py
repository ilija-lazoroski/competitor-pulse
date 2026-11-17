"""FastAPI dependencies.

The shared objects are set in setup() and cleared in teardown(); tests replace the
dependencies with app.dependency_overrides.
"""

from typing import Annotated

from fastapi import Depends

from competitor_pulse.competitor_repository import (
    CompetitorRepository,
    PostgresCompetitorRepository,
)
from competitor_pulse.configuration import ApiConfiguration
from competitor_pulse.database import Database

_database: Database | None = None
_api_configuration: ApiConfiguration | None = None


def database() -> Database:
    """Gives the database shared by all requests.

    :returns: The database opened in setup()
    :raises RuntimeError: If setup() has not run
    """
    if _database is None:
        raise RuntimeError("The database is not initialised; setup() has not run")
    return _database


def api_configuration() -> ApiConfiguration:
    """Gives the competitor API settings.

    :returns: The settings loaded in setup()
    :raises RuntimeError: If setup() has not run
    """
    if _api_configuration is None:
        raise RuntimeError("The configuration is not loaded; setup() has not run")
    return _api_configuration


def competitor_repository(
    db: Annotated[Database, Depends(database)],
    config: Annotated[ApiConfiguration, Depends(api_configuration)],
) -> CompetitorRepository:
    """Gives the competitor repository for a request.

    :param db: The shared database
    :param config: The competitor API settings
    :returns: A repository on the shared database
    """
    return PostgresCompetitorRepository(db.engine, config)
