"""Maps the application's errors to HTTP responses. Nothing else knows about HTTP statuses."""

from http import HTTPStatus
from typing import Annotated

from fastapi import FastAPI, Request
from pydantic import Field
from service_kit.api import (
    handle_structured_error,
    register_default_error_handler,
    register_timeout_error_handler,
)
from service_kit.api.responses import APIResponse, ConflictResponse, NotFoundResponse

from competitor_pulse.app.competitor_repository import (
    CompetitorAlreadyTrackedError,
    CompetitorNotTrackedError,
    InvalidPageSizeError,
)


class InvalidPageSizeResponse(APIResponse):
    """The body of a 422 response to a page size above the maximum."""

    message: Annotated[str, Field(examples=["limit must not be larger than 200"])]


def register_error_handlers(app: FastAPI):
    """Registers a handler per application error, then service-kit's default handlers.

    :param app: The FastAPI app to register the handlers on
    """

    @app.exception_handler(CompetitorNotTrackedError)
    async def competitor_not_tracked_handler(request: Request, exc: CompetitorNotTrackedError):
        return handle_structured_error(request, exc, NotFoundResponse, HTTPStatus.NOT_FOUND)

    @app.exception_handler(CompetitorAlreadyTrackedError)
    async def competitor_already_tracked_handler(
        request: Request, exc: CompetitorAlreadyTrackedError
    ):
        return handle_structured_error(request, exc, ConflictResponse, HTTPStatus.CONFLICT)

    @app.exception_handler(InvalidPageSizeError)
    async def invalid_page_size_handler(request: Request, exc: InvalidPageSizeError):
        return handle_structured_error(
            request, exc, InvalidPageSizeResponse, HTTPStatus.UNPROCESSABLE_CONTENT
        )

    register_timeout_error_handler(app)
    register_default_error_handler(app)
