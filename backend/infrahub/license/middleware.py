from __future__ import annotations

from typing import TYPE_CHECKING

from starlette.datastructures import MutableHeaders

from infrahub.license.service import read_license_status
from infrahub.license.status import notice_for
from infrahub.log import get_logger

if TYPE_CHECKING:
    from collections.abc import Callable

    from starlette.types import ASGIApp, Message, Receive, Scope, Send

    from infrahub.license.service import LicenseService

LICENSE_STATUS_HEADER = "X-Infrahub-License-Status"
ELIGIBLE_PATHS: tuple[str, ...] = ("/api", "/graphql")

log = get_logger()


class LicenseStatusHeaderMiddleware:
    """Pure-ASGI middleware that adds the license state to REST and GraphQL responses when the license notice asks for it."""

    def __init__(self, app: ASGIApp, *, license_service_provider: Callable[[], LicenseService]) -> None:
        self.app = app
        self._license_service_provider = license_service_provider
        self._failure_logged = False

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not _is_eligible(path=scope.get("path", "")):
            await self.app(scope, receive, send)
            return

        state = self._state_to_send()
        if state is None:
            await self.app(scope, receive, send)
            return

        async def send_with_header(message: Message) -> None:
            if message["type"] == "http.response.start":
                message.setdefault("headers", [])
                MutableHeaders(scope=message).append(LICENSE_STATUS_HEADER, state)
            await send(message)

        await self.app(scope, receive, send_with_header)

    def _state_to_send(self) -> str | None:
        try:
            service = self._license_service_provider()
            status = read_license_status(service=service)
            notice = notice_for(status=status, mode=service.notice_mode)
        # Top-level boundary: a defect in a replaceable license service must not fail a request, nor log on every one.
        except Exception:
            if not self._failure_logged:
                self._failure_logged = True
                log.exception("The license status header could not be computed; sending the response without it")
            return None
        return status.state.value if notice.send_header else None


def _is_eligible(path: str) -> bool:
    return any(path == prefix or path.startswith(f"{prefix}/") for prefix in ELIGIBLE_PATHS)
