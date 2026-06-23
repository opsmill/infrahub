from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Request, Response

from infrahub.health import HealthResponse, OverallStatus

if TYPE_CHECKING:
    from infrahub.health import HealthChecker

router = APIRouter()


@router.get("/health", response_model=HealthResponse, responses={503: {"model": HealthResponse}})
async def health(request: Request) -> Response:
    health_checker: HealthChecker = request.app.state.health_checker

    response_data = await health_checker.report()

    return Response(
        content=response_data.model_dump_json(),
        media_type="application/json",
        status_code=200 if response_data.status == OverallStatus.HEALTHY else 503,
    )
