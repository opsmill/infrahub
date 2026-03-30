from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from infrahub.api.health import (
    DependencyHealth,
    DependencyName,
    ErrorCategory,
    HealthResponse,
    _check_cache,
    _check_database,
    _check_message_bus,
    _classify_error,
    get_health_checks,
)
from infrahub.exceptions import InitializationError


class TestClassifyError:
    def test_timeout_error(self) -> None:
        assert _classify_error(TimeoutError()) == ErrorCategory.TIMEOUT

    def test_builtin_timeout_error(self) -> None:
        assert _classify_error(TimeoutError()) == ErrorCategory.TIMEOUT

    def test_initialization_error(self) -> None:
        assert _classify_error(InitializationError("not ready")) == ErrorCategory.NOT_INITIALIZED

    def test_connection_refused_error(self) -> None:
        assert _classify_error(ConnectionRefusedError()) == ErrorCategory.CONNECTION_REFUSED

    def test_connection_reset_error(self) -> None:
        assert _classify_error(ConnectionResetError()) == ErrorCategory.CONNECTION_REFUSED

    def test_os_error(self) -> None:
        assert _classify_error(OSError("connection failed")) == ErrorCategory.CONNECTION_REFUSED

    def test_unknown_error(self) -> None:
        assert _classify_error(RuntimeError("something")) == ErrorCategory.UNKNOWN_ERROR

    def test_value_error(self) -> None:
        assert _classify_error(ValueError("bad")) == ErrorCategory.UNKNOWN_ERROR


class TestCheckDatabase:
    @pytest.mark.anyio
    async def test_healthy(self) -> None:
        db = AsyncMock()
        db.is_healthy = AsyncMock(return_value=True)
        result = await _check_database(db=db)
        assert result.name == DependencyName.DATABASE
        assert result.status == "up"
        assert result.error is None

    @pytest.mark.anyio
    async def test_unhealthy_returns_false(self) -> None:
        db = AsyncMock()
        db.is_healthy = AsyncMock(return_value=False)
        result = await _check_database(db=db)
        assert result.name == DependencyName.DATABASE
        assert result.status == "down"
        assert result.error == ErrorCategory.UNKNOWN_ERROR

    @pytest.mark.anyio
    async def test_unhealthy_connection_refused(self) -> None:
        db = AsyncMock()
        db.is_healthy = AsyncMock(side_effect=ConnectionRefusedError())
        result = await _check_database(db=db)
        assert result.name == DependencyName.DATABASE
        assert result.status == "down"
        assert result.error == ErrorCategory.CONNECTION_REFUSED

    @pytest.mark.anyio
    async def test_unhealthy_timeout(self) -> None:
        db = AsyncMock()

        async def slow_check() -> bool:
            await asyncio.sleep(10)
            return True

        db.is_healthy = slow_check
        result = await _check_database(db=db)
        assert result.name == DependencyName.DATABASE
        assert result.status == "down"
        assert result.error == ErrorCategory.TIMEOUT


class TestCheckMessageBus:
    @pytest.mark.anyio
    async def test_healthy(self) -> None:
        bus = AsyncMock()
        bus.is_healthy = AsyncMock(return_value=True)
        result = await _check_message_bus(message_bus=bus)
        assert result.name == DependencyName.MESSAGE_BUS
        assert result.status == "up"
        assert result.error is None

    @pytest.mark.anyio
    async def test_unhealthy_returns_false(self) -> None:
        bus = AsyncMock()
        bus.is_healthy = AsyncMock(return_value=False)
        result = await _check_message_bus(message_bus=bus)
        assert result.name == DependencyName.MESSAGE_BUS
        assert result.status == "down"
        assert result.error == ErrorCategory.CONNECTION_CLOSED

    @pytest.mark.anyio
    async def test_unhealthy_initialization_error(self) -> None:
        bus = AsyncMock()
        bus.is_healthy = AsyncMock(side_effect=InitializationError("not initialized"))
        result = await _check_message_bus(message_bus=bus)
        assert result.name == DependencyName.MESSAGE_BUS
        assert result.status == "down"
        assert result.error == ErrorCategory.NOT_INITIALIZED


class TestCheckCache:
    @pytest.mark.anyio
    async def test_healthy(self) -> None:
        cache = AsyncMock()
        cache.is_healthy = AsyncMock(return_value=True)
        result = await _check_cache(cache=cache)
        assert result.name == DependencyName.CACHE
        assert result.status == "up"
        assert result.error is None

    @pytest.mark.anyio
    async def test_unhealthy_returns_false(self) -> None:
        cache = AsyncMock()
        cache.is_healthy = AsyncMock(return_value=False)
        result = await _check_cache(cache=cache)
        assert result.name == DependencyName.CACHE
        assert result.status == "down"
        assert result.error == ErrorCategory.CONNECTION_CLOSED

    @pytest.mark.anyio
    async def test_unhealthy_os_error(self) -> None:
        cache = AsyncMock()
        cache.is_healthy = AsyncMock(side_effect=OSError("connection failed"))
        result = await _check_cache(cache=cache)
        assert result.name == DependencyName.CACHE
        assert result.status == "down"
        assert result.error == ErrorCategory.CONNECTION_REFUSED


class TestGetHealthChecks:
    @pytest.mark.anyio
    async def test_all_healthy(self) -> None:
        db = AsyncMock()
        db.is_healthy = AsyncMock(return_value=True)

        service = MagicMock()
        service.message_bus = AsyncMock()
        service.message_bus.is_healthy = AsyncMock(return_value=True)
        service.cache = AsyncMock()
        service.cache.is_healthy = AsyncMock(return_value=True)

        checks = await get_health_checks(service=service, db=db)
        assert len(checks) == 3
        assert all(c.status == "up" for c in checks)
        assert all(c.error is None for c in checks)

    @pytest.mark.anyio
    async def test_one_down(self) -> None:
        db = AsyncMock()
        db.is_healthy = AsyncMock(return_value=False)

        service = MagicMock()
        service.message_bus = AsyncMock()
        service.message_bus.is_healthy = AsyncMock(return_value=True)
        service.cache = AsyncMock()
        service.cache.is_healthy = AsyncMock(return_value=True)

        checks = await get_health_checks(service=service, db=db)
        db_check = next(c for c in checks if c.name == DependencyName.DATABASE)
        bus_check = next(c for c in checks if c.name == DependencyName.MESSAGE_BUS)
        cache_check = next(c for c in checks if c.name == DependencyName.CACHE)

        assert db_check.status == "down"
        assert bus_check.status == "up"
        assert cache_check.status == "up"

    @pytest.mark.anyio
    async def test_all_down(self) -> None:
        db = AsyncMock()
        db.is_healthy = AsyncMock(return_value=False)

        service = MagicMock()
        service.message_bus = AsyncMock()
        service.message_bus.is_healthy = AsyncMock(return_value=False)
        service.cache = AsyncMock()
        service.cache.is_healthy = AsyncMock(return_value=False)

        checks = await get_health_checks(service=service, db=db)
        assert all(c.status == "down" for c in checks)


class TestHealthResponseModel:
    def test_healthy_response(self) -> None:
        checks = [
            DependencyHealth(name=DependencyName.DATABASE, status="up"),
            DependencyHealth(name=DependencyName.MESSAGE_BUS, status="up"),
            DependencyHealth(name=DependencyName.CACHE, status="up"),
        ]
        response = HealthResponse(status="healthy", checks=checks, timestamp="2026-03-30T14:00:00Z")
        data = response.model_dump()
        assert data["status"] == "healthy"
        assert len(data["checks"]) == 3
        assert all(c["error"] is None for c in data["checks"])

    def test_unhealthy_response(self) -> None:
        checks = [
            DependencyHealth(name=DependencyName.DATABASE, status="down", error=ErrorCategory.CONNECTION_REFUSED),
            DependencyHealth(name=DependencyName.MESSAGE_BUS, status="up"),
            DependencyHealth(name=DependencyName.CACHE, status="up"),
        ]
        response = HealthResponse(status="unhealthy", checks=checks, timestamp="2026-03-30T14:00:00Z")
        data = response.model_dump()
        assert data["status"] == "unhealthy"
        db_check = data["checks"][0]
        assert db_check["status"] == "down"
        assert db_check["error"] == "connection_refused"

    def test_error_categories_are_strings(self) -> None:
        """Verify error categories serialize as plain strings, not exposing internal details."""
        check = DependencyHealth(name=DependencyName.DATABASE, status="down", error=ErrorCategory.TIMEOUT)
        data = check.model_dump()
        assert data["error"] == "timeout"
        assert isinstance(data["error"], str)

    def test_no_internal_details_in_serialization(self) -> None:
        """Verify the response model cannot leak hostnames or connection strings."""
        checks = [
            DependencyHealth(name=DependencyName.DATABASE, status="down", error=ErrorCategory.CONNECTION_REFUSED),
        ]
        response = HealthResponse(status="unhealthy", checks=checks, timestamp="2026-03-30T14:00:00Z")
        json_str = response.model_dump_json()
        assert "localhost" not in json_str
        assert "neo4j://" not in json_str
        assert "redis://" not in json_str
        assert "amqp://" not in json_str
