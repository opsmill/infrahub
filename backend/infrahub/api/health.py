from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Request, Response
from starlette.status import HTTP_200_OK, HTTP_503_SERVICE_UNAVAILABLE

from infrahub.health import HealthReport, HealthStatus

if TYPE_CHECKING:
    from infrahub.health import HealthChecker

router = APIRouter(prefix="/health")


@router.get(
    "",
    response_model=HealthReport,
    responses={
        HTTP_503_SERVICE_UNAVAILABLE: {"model": HealthReport, "description": "At least one backing service is down"}
    },
)
async def get_health(request: Request) -> Response:
    """Report whether this API server can reach the services it needs, without requiring authentication."""
    health_checker: HealthChecker = request.app.state.health_checker
    report = await health_checker.report()
    return Response(
        content=report.model_dump_json(),
        media_type="application/json",
        status_code=HTTP_200_OK if report.status == HealthStatus.HEALTHY else HTTP_503_SERVICE_UNAVAILABLE,
        headers={"Cache-Control": "no-store"},
    )
