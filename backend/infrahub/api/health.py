from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from fastapi import APIRouter, Request, Response
from pydantic import BaseModel

from infrahub.exceptions import InitializationError

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase
    from infrahub.services import InfrahubServices
    from infrahub.services.adapters.cache import InfrahubCache
    from infrahub.services.adapters.message_bus import InfrahubMessageBus

HEALTH_CHECK_TIMEOUT = 3


class DependencyName(StrEnum):
    DATABASE = "database"
    MESSAGE_BUS = "message_bus"
    CACHE = "cache"


class ErrorCategory(StrEnum):
    TIMEOUT = "timeout"
    CONNECTION_REFUSED = "connection_refused"
    CONNECTION_CLOSED = "connection_closed"
    NOT_INITIALIZED = "not_initialized"
    UNKNOWN_ERROR = "unknown_error"


class DependencyHealth(BaseModel):
    name: DependencyName
    status: str
    error: ErrorCategory | None = None


class HealthResponse(BaseModel):
    status: str
    checks: list[DependencyHealth]
    timestamp: str


def _classify_error(exc: Exception) -> ErrorCategory:
    if isinstance(exc, TimeoutError | asyncio.TimeoutError):
        return ErrorCategory.TIMEOUT
    if isinstance(exc, InitializationError):
        return ErrorCategory.NOT_INITIALIZED
    if isinstance(exc, ConnectionRefusedError | ConnectionResetError | OSError):
        return ErrorCategory.CONNECTION_REFUSED
    return ErrorCategory.UNKNOWN_ERROR


async def _check_database(db: InfrahubDatabase) -> DependencyHealth:
    try:
        healthy = await asyncio.wait_for(db.is_healthy(), timeout=HEALTH_CHECK_TIMEOUT)
        if healthy:
            return DependencyHealth(name=DependencyName.DATABASE, status="up")
        return DependencyHealth(name=DependencyName.DATABASE, status="down", error=ErrorCategory.UNKNOWN_ERROR)
    except Exception as exc:
        return DependencyHealth(name=DependencyName.DATABASE, status="down", error=_classify_error(exc))


async def _check_message_bus(message_bus: InfrahubMessageBus) -> DependencyHealth:
    try:
        healthy = await asyncio.wait_for(message_bus.is_healthy(), timeout=HEALTH_CHECK_TIMEOUT)
        if healthy:
            return DependencyHealth(name=DependencyName.MESSAGE_BUS, status="up")
        return DependencyHealth(name=DependencyName.MESSAGE_BUS, status="down", error=ErrorCategory.CONNECTION_CLOSED)
    except Exception as exc:
        return DependencyHealth(name=DependencyName.MESSAGE_BUS, status="down", error=_classify_error(exc))


async def _check_cache(cache: InfrahubCache) -> DependencyHealth:
    try:
        healthy = await asyncio.wait_for(cache.is_healthy(), timeout=HEALTH_CHECK_TIMEOUT)
        if healthy:
            return DependencyHealth(name=DependencyName.CACHE, status="up")
        return DependencyHealth(name=DependencyName.CACHE, status="down", error=ErrorCategory.CONNECTION_CLOSED)
    except Exception as exc:
        return DependencyHealth(name=DependencyName.CACHE, status="down", error=_classify_error(exc))


async def get_health_checks(service: InfrahubServices, db: InfrahubDatabase) -> list[DependencyHealth]:
    checks = await asyncio.gather(
        _check_database(db=db),
        _check_message_bus(message_bus=service.message_bus),
        _check_cache(cache=service.cache),
        return_exceptions=False,
    )
    return list(checks)


router = APIRouter()


@router.get("/health", response_model=HealthResponse, responses={503: {"model": HealthResponse}})
async def health(request: Request) -> Response:
    try:
        service: InfrahubServices = request.app.state.service
        db: InfrahubDatabase = request.app.state.db
    except AttributeError:
        checks = [
            DependencyHealth(name=DependencyName.DATABASE, status="down", error=ErrorCategory.NOT_INITIALIZED),
            DependencyHealth(name=DependencyName.MESSAGE_BUS, status="down", error=ErrorCategory.NOT_INITIALIZED),
            DependencyHealth(name=DependencyName.CACHE, status="down", error=ErrorCategory.NOT_INITIALIZED),
        ]
        response_data = HealthResponse(
            status="unhealthy",
            checks=checks,
            timestamp=datetime.now(tz=UTC).isoformat(),
        )
        return Response(
            content=response_data.model_dump_json(),
            media_type="application/json",
            status_code=503,
        )

    checks = await get_health_checks(service=service, db=db)
    all_healthy = all(check.status == "up" for check in checks)

    response_data = HealthResponse(
        status="healthy" if all_healthy else "unhealthy",
        checks=checks,
        timestamp=datetime.now(tz=UTC).isoformat(),
    )

    return Response(
        content=response_data.model_dump_json(),
        media_type="application/json",
        status_code=200 if all_healthy else 503,
    )
