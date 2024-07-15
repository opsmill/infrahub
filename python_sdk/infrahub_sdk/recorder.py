from __future__ import annotations

import enum
from pathlib import Path
from typing import Protocol, runtime_checkable

import httpx
import ujson
from pydantic_settings import BaseSettings, SettingsConfigDict

from infrahub_sdk.utils import generate_request_filename


class RecorderType(str, enum.Enum):
    NONE = "none"
    JSON = "json"


@runtime_checkable
class Recorder(Protocol):
    def record(self, response: httpx.Response) -> None:
        """Record the response from Infrahub"""


class NoRecorder:
    @staticmethod
    def record(response: httpx.Response) -> None:
        """The NoRecorder just silently returns"""

    @classmethod
    def default(cls) -> NoRecorder:
        return cls()


class JSONRecorder(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="INFRAHUB_JSON_RECORDER_")
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
            "response_content": response.content.decode("utf-8"),
            "request_content": response.request.content.decode("utf-8"),
        }

        with Path(f"{self.directory}/{filename}.json").open(mode="w", encoding="utf-8") as fobj:
            ujson.dump(data, fobj, indent=4, sort_keys=True)

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
