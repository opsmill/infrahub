from __future__ import annotations

import enum
import json
from typing import Protocol, runtime_checkable, Set

import httpx

try:
    from pydantic import v1 as pydantic  # type: ignore[attr-defined]
    from pydantic.v1.fields import ModelField
except ImportError:
    import pydantic  # type: ignore[no-redef]
    from pydantic.fields import ModelField

from infrahub_sdk.utils import generate_request_filename


class RecorderType(str, enum.Enum):
    NONE = "none"
    JSON = "json"


@runtime_checkable
class Recorder(Protocol):
    def record(self, response: httpx.Response) -> None:
        """Record the response from Infrahub"""

    @classmethod
    def __modify_schema__(cls, field_schema: Dict[str, Set[str]], field: Optional[ModelField]):
        field.type_ = str


class NoRecorder:
    @staticmethod
    def record(response: httpx.Response) -> None:
        """The NoRecorder just silently returns"""

    @classmethod
    def default(cls) -> NoRecorder:
        return cls()


class JSONRecorder(pydantic.BaseSettings):
    directory: str = "."
    host: str = ""

    def record(self, response: httpx.Response) -> None:
        self._set_url_host(response)
        filename = generate_request_filename(response.request)
        data = {
            "status_code": response.status_code,
            "method": response.request.method,
            "url": str(response.request.url),
            "headers": dict(response.request.headers),
            "response_content": response.content.decode("UTF-8"),
            "request_content": response.request.content.decode("UTF-8"),
        }

        with open(f"{self.directory}/{filename}.json", "w", encoding="UTF-8") as fobj:
            json.dump(data, fobj, indent=4, sort_keys=True)

    def _set_url_host(self, response: httpx.Response) -> None:
        if not self.host:
            return
        original = str(response.request.url)
        if response.request.url.port:
            modified = original.replace(
                f"{response.request.url.scheme}://{response.request.url.host}:",
                f"{response.request.url.scheme}://{self.host}:",
            )
        else:
            modified = original.replace(
                f"{response.request.url.scheme}://{response.request.url.host}/",
                f"{response.request.url.scheme}://{self.host}/",
            )

        response.request.url = httpx.URL(url=modified)

    class Config:
        env_prefix = "INFRAHUB_SDK_JSON_RECORDER_"
        case_sensitive = False
