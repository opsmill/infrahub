from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock

if TYPE_CHECKING:
    from starlette.responses import JSONResponse

import pytest
from pydantic import BaseModel, ValidationError, field_validator
from starlette.datastructures import State
from starlette.requests import Request
from ujson import loads

from infrahub.api.exception_handlers import generic_api_exception_handler, permission_denied_exception_handler
from infrahub.auth import AccountSession, AuthType
from infrahub.exceptions import Error, PermissionDeniedError
from infrahub.log_forwarding.models import LogForwardingContext
from infrahub.log_forwarding.service import LogForwardingService
from infrahub.services import InfrahubServices


def get_response_body(response: JSONResponse) -> dict[str, Any]:
    """Extract and decode response body as JSON dict."""
    body = response.body
    assert isinstance(body, bytes)
    return loads(body.decode())


class ModelForTesting(BaseModel):
    field_1: str | None = None
    field_2: str

    @field_validator("field_1", mode="before")
    @classmethod
    def always_fail(cls, value: str | None = None) -> str:
        raise ValueError("this is the error message")

    @field_validator("field_2", mode="before")
    @classmethod
    def always_fail_more(cls, value: str | None = None) -> str:
        raise ValueError("another error message")


class MockError(Error):
    HTTP_CODE = 418
    DESCRIPTION = "the teapot error"

    def __init__(self, message: str | None) -> None:
        self.message = message or ""


@dataclass
class RequestFixture:
    request: Request
    mock_log_forwarding: MagicMock
    account_session: AccountSession


def _make_request(
    *,
    path: str = "/api/test",
    client_host: str = "10.0.0.1",
    app_state: State | None = None,
) -> Request:
    return Request(
        scope={
            "type": "http",
            "method": "POST",
            "path": path,
            "query_string": b"",
            "root_path": "",
            "headers": [],
            "server": ("testserver", 80),
            "client": (client_host, 12345),
            "app": MagicMock(state=app_state or State()),
        },
    )


@pytest.fixture
def request_fixture() -> RequestFixture:
    mock_lf = MagicMock(spec=LogForwardingService)
    account_session = AccountSession(account_id="user-1", auth_type=AuthType.JWT)

    service_mock = MagicMock(spec=InfrahubServices)
    service_mock.log_forwarding = mock_lf
    app_state = State()
    app_state.service = service_mock

    request = _make_request(path="/api/schema/load", app_state=app_state)
    request.state.account_session = account_session
    request.state.branch_name = "main"

    return RequestFixture(
        request=request,
        mock_log_forwarding=mock_lf,
        account_session=account_session,
    )


class TestAPIExceptionHandler:
    def setup_method(self) -> None:
        self.error_message = "Value error, this is the error message"

    async def test_plain_exception_error(self) -> None:
        exception = ValueError(self.error_message)

        error_response = await generic_api_exception_handler(_make_request(), exception)

        error_dict = get_response_body(error_response)
        assert error_dict["errors"] == [{"message": self.error_message, "extensions": {"code": 500}}]

    async def test_pydantic_validation_error(self) -> None:
        error_message_2 = "Value error, another error message"
        exception: ValidationError | None = None
        try:
            ModelForTesting(field_1="abc", field_2="def")
        except ValidationError as exc:
            exception = exc

        assert exception is not None
        error_response = await generic_api_exception_handler(_make_request(), exception, http_code=400)

        error_dict = get_response_body(error_response)
        assert {"message": self.error_message, "extensions": {"code": 400}} in error_dict["errors"]
        assert {"message": error_message_2, "extensions": {"code": 400}} in error_dict["errors"]
        assert len(error_dict) == 2

    async def test_infrahub_api_error(self) -> None:
        exception = MockError(self.error_message)

        error_response = await generic_api_exception_handler(_make_request(), exception)

        error_dict = get_response_body(error_response)
        assert error_dict["errors"] == [{"message": self.error_message, "extensions": {"code": 418}}]

    async def test_infrahub_api_error_default_message(self) -> None:
        exception = MockError(None)

        error_response = await generic_api_exception_handler(_make_request(), exception)

        error_dict = get_response_body(error_response)
        assert error_dict["errors"] == [{"message": "the teapot error", "extensions": {"code": 418}}]

    async def test_infrahub_api_error_code_override(self) -> None:
        exception = MockError(None)

        error_response = await generic_api_exception_handler(_make_request(), exception, http_code=500)

        error_dict = get_response_body(error_response)
        assert error_dict["errors"] == [{"message": "the teapot error", "extensions": {"code": 418}}]


class TestPermissionDeniedForwarding:
    async def test_forwards_permission_denied_to_log_forwarding(self, request_fixture: RequestFixture) -> None:
        exc = PermissionDeniedError("not allowed")

        await permission_denied_exception_handler(request_fixture.request, exc)

        request_fixture.mock_log_forwarding.forward_exception.assert_called_once()
        call_kwargs = request_fixture.mock_log_forwarding.forward_exception.call_args.kwargs
        assert call_kwargs["exception"] is exc
        ctx = call_kwargs["context"]
        assert isinstance(ctx, LogForwardingContext)
        assert ctx.account_session is request_fixture.account_session
        assert ctx.branch_name == "main"
        assert ctx.ip_address == "10.0.0.1"
        assert ctx.request_path == "/api/schema/load"

    async def test_returns_403_response(self, request_fixture: RequestFixture) -> None:
        response = await permission_denied_exception_handler(request_fixture.request, PermissionDeniedError("denied"))

        error_dict = get_response_body(response)
        assert response.status_code == 403
        assert error_dict["errors"] == [{"message": "denied", "extensions": {"code": 403}}]

    async def test_no_service_does_not_raise(self) -> None:
        app_state = State()
        app_state.service = None
        request = _make_request(app_state=app_state)

        response = await permission_denied_exception_handler(request, PermissionDeniedError("denied"))

        assert response.status_code == 403

    async def test_no_log_forwarding_does_not_raise(self, request_fixture: RequestFixture) -> None:
        request_fixture.mock_log_forwarding = None  # type: ignore[assignment]
        request_fixture.request.app.state.service.log_forwarding = None

        response = await permission_denied_exception_handler(request_fixture.request, PermissionDeniedError("denied"))

        assert response.status_code == 403

    async def test_forwarding_failure_does_not_affect_response(self, request_fixture: RequestFixture) -> None:
        request_fixture.mock_log_forwarding.forward_exception.side_effect = RuntimeError("boom")

        response = await permission_denied_exception_handler(request_fixture.request, PermissionDeniedError("denied"))

        assert response.status_code == 403

    async def test_missing_account_session_on_state(self, request_fixture: RequestFixture) -> None:
        del request_fixture.request.state.account_session

        await permission_denied_exception_handler(request_fixture.request, PermissionDeniedError("denied"))

        ctx = request_fixture.mock_log_forwarding.forward_exception.call_args.kwargs["context"]
        assert ctx.account_session is None

    async def test_missing_branch_name_on_state(self, request_fixture: RequestFixture) -> None:
        del request_fixture.request.state.branch_name

        await permission_denied_exception_handler(request_fixture.request, PermissionDeniedError("denied"))

        ctx = request_fixture.mock_log_forwarding.forward_exception.call_args.kwargs["context"]
        assert not ctx.branch_name

    async def test_no_client_uses_empty_ip(self, request_fixture: RequestFixture) -> None:
        request_fixture.request.scope["client"] = None

        await permission_denied_exception_handler(request_fixture.request, PermissionDeniedError("denied"))

        ctx = request_fixture.mock_log_forwarding.forward_exception.call_args.kwargs["context"]
        assert not ctx.ip_address
