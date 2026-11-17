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
    """The body of a request to start tracking a competitor."""

    id: CompetitorId


@router.get("", summary="List tracked competitors")
async def list_competitors(repository: Repository) -> list[Competitor]:
    """Lists the tracked competitors and whether each one changed recently.

    :param repository: The competitor repository
    :returns: The tracked competitors, ordered by id
    """
    return await repository.list_tracked()


@router.post(
    "",
    status_code=HTTPStatus.CREATED,
    summary="Start tracking a competitor",
    responses=get_standard_responses([HTTPStatus.CONFLICT]),
)
async def add_competitor(body: CompetitorCreate, repository: Repository) -> CompetitorCreate:
    """Starts tracking a competitor; one that was removed comes back with its history.

    The id is not checked with the source: the first poll shows whether the source knows it.

    :param body: The id of the competitor to track
    :param repository: The competitor repository
    :returns: The id of the competitor now tracked
    :raises CompetitorAlreadyTrackedError: If the competitor is tracked already (409)
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
    """Stops polling a competitor; its history is kept for the retention period.

    :param competitor_id: The competitor to stop tracking
    :param repository: The competitor repository
    :raises CompetitorNotTrackedError: If the competitor is not tracked (404)
    """
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
    """Lists one page of a competitor's snapshots, newest first.

    :param competitor_id: The competitor whose snapshots to list
    :param repository: The competitor repository
    :param limit: The page size; the configured default if not given
    :param before: Only snapshots older than this snapshot id; the newest page if not given
    :returns: The snapshots of the page, newest first
    :raises CompetitorNotTrackedError: If the competitor is not tracked (404)
    :raises InvalidPageSizeError: If `limit` is above the configured maximum (422)
    """
    return await repository.list_snapshots(competitor_id, limit, before)
