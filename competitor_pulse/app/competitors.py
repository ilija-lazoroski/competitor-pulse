"""The competitor API from the brief. The endpoints are stubs that answer 501 for now."""

from datetime import datetime
from http import HTTPStatus
from typing import Annotated, NoReturn

from fastapi import APIRouter, HTTPException, Path
from pydantic import Field
from service_kit import ServiceKitBaseModel

router = APIRouter(prefix="/api/competitors", tags=["competitors"])

# Lowercase slugs like "acme-crm". The id goes into the source URL (/listings/{id}), so
# slashes, dots and other path characters must never get through.
COMPETITOR_ID_PATTERN = r"^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?$"

CompetitorId = Annotated[str, Field(pattern=COMPETITOR_ID_PATTERN, examples=["acme-crm"])]
CompetitorIdPath = Annotated[str, Path(pattern=COMPETITOR_ID_PATTERN, examples=["acme-crm"])]


class Competitor(ServiceKitBaseModel):
    id: CompetitorId


class CompetitorCreate(ServiceKitBaseModel):
    id: CompetitorId


class Snapshot(ServiceKitBaseModel):
    fetchedAt: datetime
    title: str | None
    tagline: str | None
    price: str | None
    description: str | None
    changed: bool = Field(description="Differs in a way that matters from the previous snapshot")
    summary: str | None = Field(description="Plain-English summary of the change, if available")


def _not_implemented() -> NoReturn:
    raise HTTPException(HTTPStatus.NOT_IMPLEMENTED, "Not implemented yet")


@router.get("", summary="List tracked competitors")
async def list_competitors() -> list[Competitor]:
    _not_implemented()


@router.post("", status_code=HTTPStatus.CREATED, summary="Start tracking a competitor")
async def add_competitor(body: CompetitorCreate) -> Competitor:
    _not_implemented()


@router.delete(
    "/{competitor_id}", status_code=HTTPStatus.NO_CONTENT, summary="Stop tracking a competitor"
)
async def remove_competitor(competitor_id: CompetitorIdPath) -> None:
    _not_implemented()


@router.get("/{competitor_id}/snapshots", summary="A competitor's snapshots, newest first")
async def list_snapshots(competitor_id: CompetitorIdPath) -> list[Snapshot]:
    _not_implemented()
