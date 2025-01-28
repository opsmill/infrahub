from typing import Any

import httpx

from infrahub.services.adapters.http import InfrahubHTTP


class MemoryHTTP(InfrahubHTTP):
    def __init__(self) -> None:
        self._get_response: dict[str, httpx.Response] = {}
        self._post_response: dict[str, httpx.Response] = {}

    async def get(
        self,
        url: str,
        headers: dict[str, Any] | None = None,
    ) -> httpx.Response:
        return self._get_response[url]

    async def post(
        self,
        url: str,
        data: Any | None = None,
        json: Any | None = None,
        headers: dict[str, Any] | None = None,
        verify: bool | None = None,
    ) -> httpx.Response:
        return self._post_response[url]

    def add_get_response(self, url: str, response: httpx.Response) -> None:
        self._get_response[url] = response

    def add_post_response(self, url: str, response: httpx.Response) -> None:
        self._post_response[url] = response
