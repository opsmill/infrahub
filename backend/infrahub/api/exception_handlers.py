from __future__ import annotations

from typing import TYPE_CHECKING, Any

from fastapi.responses import JSONResponse
from pydantic import ValidationError

from infrahub.auth.session import AccountSession
from infrahub.exceptions import Error, ForwardableError
from infrahub.graphql.error_formatter import build_catalogue_extensions
from infrahub.log_forwarding.models import LogForwardingContext
from infrahub.services import InfrahubServices

if TYPE_CHECKING:
    from starlette.requests import Request


GRAPHQL_PATH_PREFIX = "/graphql"


def _graphql_envelope(exc: Exception, messages: list[str], http_code: int) -> dict[str, Any]:
    """Build the GraphQL-shaped error response body."""
    extensions = build_catalogue_extensions(exc)
    # When the catalogue cannot resolve a more specific status (e.g. pydantic.ValidationError
    # mapped to UNDEFINED_ERROR), surface the HTTP code FastAPI is about to return.
    if extensions["http_status"] == 500 and http_code != 500:
        extensions["http_status"] = http_code
    return {
        "data": None,
        "errors": [{"message": message, "extensions": dict(extensions)} for message in messages],
    }


def _rest_envelope(messages: list[str], http_code: int) -> dict[str, Any]:
    """Preserve the legacy REST response shape (integer ``extensions.code``)."""
    return {
        "data": None,
        "errors": [{"message": message, "extensions": {"code": http_code}} for message in messages],
    }


def _extract_messages(exc: Exception) -> tuple[list[str], int]:
    http_code = 500
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
    return messages, http_code


async def generic_api_exception_handler(request: Request, exc: Exception, http_code: int = 500) -> JSONResponse:
    """Generic API Exception handler.

    For requests hitting the GraphQL endpoint, the response body uses the GraphQL error envelope
    (``extensions.code`` as a string drawn from the catalogue, plus ``http_status`` and ``data``).
    REST routes keep the legacy shape with an integer ``extensions.code``.
    """
    messages, resolved_http_code = _extract_messages(exc)
    if http_code == 500 and resolved_http_code != 500:
        http_code = resolved_http_code

    if request.url.path.startswith(GRAPHQL_PATH_PREFIX):
        body = _graphql_envelope(exc=exc, messages=messages, http_code=http_code)
    else:
        body = _rest_envelope(messages=messages, http_code=http_code)

    return JSONResponse(status_code=http_code, content=body)


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
