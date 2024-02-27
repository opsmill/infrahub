import enum
from typing import Any, Dict, Optional, Protocol, runtime_checkable, Set

import httpx

try:
    from pydantic.v1.fields import ModelField
except ImportError:
    from pydantic.fields import ModelField


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
    ) -> httpx.Response:
        ...

    @classmethod
    def __modify_schema__(cls, field_schema: Dict[str, Set[str]], field: Optional[ModelField]):
        field.type_ = str


@runtime_checkable
class AsyncRequester(Protocol):
    async def __call__(
        self,
        url: str,
        method: HTTPMethod,
        headers: Dict[str, Any],
        timeout: int,
        payload: Optional[Dict] = None,
    ) -> httpx.Response:
        ...

    @classmethod
    def __modify_schema__(cls, field_schema: Dict[str, Set[str]], field: Optional[ModelField]):
        field.type_ = str
