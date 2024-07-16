import enum
from logging import Logger
from typing import Any, Optional, Protocol, Union, runtime_checkable

import httpx


class HTTPMethod(str, enum.Enum):
    GET = "get"
    POST = "post"


class RequesterTransport(str, enum.Enum):
    HTTPX = "httpx"
    JSON = "json"


@runtime_checkable
class SyncRequester(Protocol):
    def __call__(
        self,
        url: str,
        method: HTTPMethod,
        headers: dict[str, Any],
        timeout: int,
        payload: Optional[dict] = None,
    ) -> httpx.Response: ...


@runtime_checkable
class AsyncRequester(Protocol):
    async def __call__(
        self,
        url: str,
        method: HTTPMethod,
        headers: dict[str, Any],
        timeout: int,
        payload: Optional[dict] = None,
    ) -> httpx.Response: ...


@runtime_checkable
class InfrahubLogger(Protocol):
    def debug(self, event: Optional[str] = None, *args: Any, **kw: Any) -> Any:
        """Send a debug event"""

    def info(self, event: Optional[str] = None, *args: Any, **kw: Any) -> Any:
        """Send an info event"""

    def warning(self, event: Optional[str] = None, *args: Any, **kw: Any) -> Any:
        """Send a warning event"""

    def error(self, event: Optional[str] = None, *args: Any, **kw: Any) -> Any:
        """Send an error event."""

    def critical(self, event: Optional[str] = None, *args: Any, **kw: Any) -> Any:
        """Send a critical event."""

    def exception(self, event: Optional[str] = None, *args: Any, **kw: Any) -> Any:
        """Send an exception event."""


InfrahubLoggers = Union[InfrahubLogger, Logger]
