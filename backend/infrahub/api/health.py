from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Request, Response

from infrahub.health import HealthResponse, OverallStatus, health_report

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase
    from infrahub.services import InfrahubServices

router = APIRouter()


@router.get("/health", response_model=HealthResponse, responses={503: {"model": HealthResponse}})
async def health(request: Request) -> Response:
    service: InfrahubServices = request.app.state.service
    db: InfrahubDatabase = request.app.state.db

    response_data = await health_report(service=service, db=db)

    return Response(
        content=response_data.model_dump_json(),
        media_type="application/json",
        status_code=200 if response_data.status == OverallStatus.HEALTHY else 503,
    )
