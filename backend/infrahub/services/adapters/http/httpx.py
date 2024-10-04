from __future__ import annotations

import ssl
from functools import cached_property
from typing import TYPE_CHECKING, Any

import httpx

from infrahub import config
from infrahub.exceptions import HTTPServerError, HTTPServerSSLError, HTTPServerTimeoutError
from infrahub.services.adapters.http import InfrahubHTTP

if TYPE_CHECKING:
    from infrahub.services import InfrahubServices


class HttpxAdapter(InfrahubHTTP):
    settings: config.HTTPSettings
    service: InfrahubServices

    async def initialize(self, service: InfrahubServices) -> None:
        """Initialize the HTTP adapter"""
        self.service = service
        self.settings = config.SETTINGS.http

        # Cache the context during init, this is to avoid issue when a CA bundle might be accessible
        # when Infrahub initializes but then removed before the first external HTTP call is made.
        _ = self.tls_context

    @cached_property
    def tls_context(self) -> ssl.SSLContext:
        return self.settings.get_tls_context()

    def verify_tls(self, verify: bool | None = None) -> bool | ssl.SSLContext:
        if verify is False:
            return False

        return self.tls_context

    async def _request(
        self,
        method: str,
        url: str,
        data: Any | None = None,
        json: Any | None = None,
        headers: dict[str, Any] | None = None,
        verify: bool | None = None,
    ) -> httpx.Response:
        """Returns an httpx.Response object or raises HTTPServerError or child classes."""
        params: dict[str, Any] = {}
        if data:
            params["data"] = data
        if json:
            params["json"] = json
        async with httpx.AsyncClient(verify=self.verify_tls(verify=verify)) as client:
            try:
                response = await client.request(
                    method=method,
                    url=url,
                    headers=headers,
                    timeout=self.settings.timeout,
                    **params,
                )
            except ssl.SSLCertVerificationError as exc:
                self.service.log.info(f"TLS verification failed for connection to {url}")
                raise HTTPServerSSLError(message=f"Unable to validate TLS certificate for connection to {url}") from exc
            except httpx.ReadTimeout as exc:
                self.service.log.info(f"Connection timed out when trying to reach {url}")
                raise HTTPServerTimeoutError(
                    message=f"Connection to {url} timed out after {self.settings.timeout}"
                ) from exc
            except httpx.RequestError as exc:
                # Catch all error from httpx
                self.service.log.warning(f"Unhandled HTTP error for {url} ({exc})")
                raise HTTPServerError(message=f"Unknown http error when connecting to {url}") from exc

        return response

    async def get(
        self,
        url: str,
        headers: dict[str, Any] | None = None,
    ) -> httpx.Response:
        return await self._request(
            method="get",
            url=url,
            headers=headers,
        )

    async def post(
        self,
        url: str,
        data: Any | None = None,
        json: Any | None = None,
        headers: dict[str, Any] | None = None,
        verify: bool | None = None,
    ) -> httpx.Response:
        return await self._request(method="post", url=url, data=data, json=json, headers=headers, verify=verify)
