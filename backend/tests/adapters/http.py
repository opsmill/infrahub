from __future__ import annotations

from typing import TYPE_CHECKING, Any

import httpx

from infrahub.services.adapters.http import InfrahubHTTP

if TYPE_CHECKING:
    import ssl

    import httpx


class MemoryHTTP(InfrahubHTTP):
    def __init__(self) -> None:
        self._get_response: dict[str, httpx.Response] = {}
        self._post_response: dict[str, httpx.Response | Exception] = {}

    def verify_tls(self, verify: bool | None = None) -> bool | ssl.SSLContext:
        return False

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
        registered = self._post_response[url]
        if isinstance(registered, Exception):
            raise registered
        return registered

    def add_get_response(self, url: str, response: httpx.Response) -> None:
        self._get_response[url] = response

    def add_post_response(self, url: str, response: httpx.Response | Exception) -> None:
        """Register what a POST to `url` yields: a response to return, or an error to raise."""
        self._post_response[url] = response
