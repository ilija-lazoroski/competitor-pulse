from http import HTTPStatus
from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from service_kit import ServiceKitBaseModel
from service_kit.api import get_standard_responses
from service_kit.logging import logger

from competitor_pulse.app.dependencies import database
from competitor_pulse.database import Database

router = APIRouter(tags=["health"])


class HealthResponse(ServiceKitBaseModel):
    status: Literal["ok"]


class UnavailableResponse(ServiceKitBaseModel):
    status: Literal["unavailable"]


@router.get(
    "/health",
    summary="Liveness check",
    responses=get_standard_responses([HTTPStatus.INTERNAL_SERVER_ERROR]),
)
async def health() -> HealthResponse:
    """Returns ok while the API process is up. Does not check the database."""
    return HealthResponse(status="ok")


@router.get(
    "/health/db",
    summary="Database check",
    responses={HTTPStatus.SERVICE_UNAVAILABLE: {"model": UnavailableResponse}},
)
async def health_db(db: Annotated[Database, Depends(database)]) -> HealthResponse:
    """Returns ok if the database answers SELECT 1, otherwise 503."""
    try:
        await db.ping()
    except Exception as err:
        # Only the type and message: no traceback (and its local variables) in the log.
        logger.error("Database check failed", error_type=type(err).__name__, error=str(err))
        return JSONResponse(  # type: ignore[return-value]
            status_code=HTTPStatus.SERVICE_UNAVAILABLE,
            content=UnavailableResponse(status="unavailable").to_json_dict(),
        )

    return HealthResponse(status="ok")
