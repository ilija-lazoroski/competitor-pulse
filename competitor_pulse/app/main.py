from contextlib import asynccontextmanager
from pathlib import Path
from typing import Final

from fastapi import FastAPI
from service_kit.api import (
    RequestIDMiddleware,
    RequestLogMiddleware,
    bootstrap_logging,
    launch_uvicorn,
    register_default_error_handler,
    register_timeout_error_handler,
)
from service_kit.logging import log_startup_information, logger

from competitor_pulse.app import competitors, dependencies, health
from competitor_pulse.configuration import CompetitorPulseConfiguration, load_configuration
from competitor_pulse.database import Database

PROJECT_NAME: Final[str] = "CompetitorPulse API"
API_VERSION: Final[str] = "0.1.0"
ENTRYPOINT: Final[str] = "competitor_pulse.app.main:app"

# Used by log_startup_information() when git is not available (e.g. in Docker).
GIT_STATUS_YAML_PATH: Final[Path] = Path.cwd() / "GIT_STATUS.yaml"


@asynccontextmanager
async def lifespan(_app: FastAPI):
    config = await setup(_app)
    yield
    await teardown(_app, config)


async def setup(_app: FastAPI) -> CompetitorPulseConfiguration:
    # Uvicorn forks the process, so the configuration is loaded again here.
    config = load_configuration()
    await bootstrap_logging(_app, config)
    log_startup_information(GIT_STATUS_YAML_PATH)

    database = Database.from_configuration(config.database)
    await database.open()
    dependencies._database = database

    return config


async def teardown(_app: FastAPI, _config: CompetitorPulseConfiguration):
    logger.info(f"Shutting down {PROJECT_NAME}...")
    await dependencies.database().close()
    dependencies._database = None


app = FastAPI(lifespan=lifespan, title=PROJECT_NAME, version=API_VERSION)

# Error handlers must be registered before the RequestLogMiddleware, otherwise responses to
# requests that raise uncaught exceptions are not logged properly.
register_timeout_error_handler(app)
register_default_error_handler(app)

# Middlewares run in the reverse order in which they are added.
app.add_middleware(RequestLogMiddleware)
app.add_middleware(RequestIDMiddleware)

app.include_router(health.router)
app.include_router(competitors.router)


def main():
    launch_uvicorn(PROJECT_NAME, ENTRYPOINT, load_configuration())
