from __future__ import annotations

from typing import TYPE_CHECKING, Any

from fastapi.responses import JSONResponse
from pydantic import ValidationError

from infrahub.auth import AccountSession
from infrahub.exceptions import Error, ForwardableError
from infrahub.log_forwarding.models import LogForwardingContext
from infrahub.services import InfrahubServices

if TYPE_CHECKING:
    from starlette.requests import Request


async def generic_api_exception_handler(_: Request, exc: Exception, http_code: int = 500) -> JSONResponse:
    """Generic API Exception handler."""
    if isinstance(exc, Error):
        if exc.HTTP_CODE:
            http_code = exc.HTTP_CODE
        if isinstance(exc.errors, list):
            messages = exc.errors
        else:
            messages = [str(exc.message) if exc.message else exc.DESCRIPTION]
    elif isinstance(exc, ValidationError):
        messages = [ed["msg"] for ed in exc.errors()]
    else:
        messages = [str(exc)]
    error_dict: dict[str, Any] = {
        "data": None,
        "errors": [{"message": message, "extensions": {"code": http_code}} for message in messages],
    }

    return JSONResponse(status_code=http_code, content=error_dict)


async def log_forwarding_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Forward ForwardableError to log forwarding, then delegate to the generic handler."""
    if isinstance(exc, ForwardableError) and not exc.log_forwarded:
        _forward_exception(request, exc)
    return await generic_api_exception_handler(request, exc)


def _forward_exception(request: Request, exc: ForwardableError) -> None:
    service = getattr(request.app.state, "service", None)
    if not isinstance(service, InfrahubServices):
        return

    log_forwarding = service.log_forwarding
    if log_forwarding is None:
        return

    raw_account_session = getattr(request.state, "account_session", None)
    account_session = raw_account_session if isinstance(raw_account_session, AccountSession) else None
    branch_name: str = getattr(request.state, "branch_name", "")

    context = LogForwardingContext(
        account_session=account_session,
        branch_name=branch_name,
        ip_address=request.client.host if request.client else "",
        request_path=request.url.path,
    )
    log_forwarding.forward_exception(exception=exc, context=context)
    exc.log_forwarded = True
