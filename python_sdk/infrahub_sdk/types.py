import enum
from typing import Any, Dict, Optional, Protocol, runtime_checkable

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
        headers: Dict[str, Any],
        timeout: int,
        payload: Optional[Dict] = None,
    ) -> httpx.Response: ...


@runtime_checkable
class AsyncRequester(Protocol):
    async def __call__(
        self,
        url: str,
        method: HTTPMethod,
        headers: Dict[str, Any],
        timeout: int,
        payload: Optional[Dict] = None,
    ) -> httpx.Response: ...
