"""The competitor API from the brief. Each endpoint makes one repository call."""

from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from service_kit.api import get_standard_responses

from competitor_pulse.app.dependencies import competitor_repository
from competitor_pulse.competitor_repository import CompetitorRepository
from competitor_pulse.models import ApiModel, Competitor, Snapshot
from competitor_pulse.types import CompetitorId

router = APIRouter(prefix="/api/competitors", tags=["competitors"])

Repository = Annotated[CompetitorRepository, Depends(competitor_repository)]


class CompetitorCreate(ApiModel):
    id: CompetitorId


@router.get("", summary="List tracked competitors")
async def list_competitors(repository: Repository) -> list[Competitor]:
    return await repository.list_tracked()


@router.post(
    "",
    status_code=HTTPStatus.CREATED,
    summary="Start tracking a competitor",
    responses=get_standard_responses([HTTPStatus.CONFLICT]),
)
async def add_competitor(body: CompetitorCreate, repository: Repository) -> CompetitorCreate:
    """The id is not checked with the source: the first poll shows whether the source knows it.

    A competitor that was removed is tracked again, with its history.
    """
    await repository.add(body.id)
    return body


@router.delete(
    "/{competitor_id}",
    status_code=HTTPStatus.NO_CONTENT,
    summary="Stop tracking a competitor",
    responses=get_standard_responses([HTTPStatus.NOT_FOUND]),
)
async def remove_competitor(competitor_id: CompetitorId, repository: Repository) -> None:
    """Polling stops; the history is kept until it is older than the retention period."""
    await repository.remove(competitor_id)


@router.get(
    "/{competitor_id}/snapshots",
    summary="A competitor's snapshots, newest first",
    responses=get_standard_responses([HTTPStatus.NOT_FOUND]),
)
async def list_snapshots(
    competitor_id: CompetitorId,
    repository: Repository,
    limit: Annotated[int | None, Query(ge=1, description="Page size")] = None,
    before: Annotated[
        int | None, Query(ge=1, description="Only snapshots older than this snapshot id")
    ] = None,
) -> list[Snapshot]:
    return await repository.list_snapshots(competitor_id, limit, before)
