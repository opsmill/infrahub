from __future__ import annotations

import ssl
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

    def verify_tls(self, verify: bool | None = None) -> bool:
        if verify is not None:
            return verify

        if self.settings.tls_insecure is True:
            return False

        return True

    async def _request(
        self,
        method: str,
        url: str,
        json: Any | None = None,
        headers: dict[str, Any] | None = None,
        verify: bool | None = None,
    ) -> httpx.Response:
        """Returns an httpx.Response object or raises HTTPServerError or child classes."""
        params: dict[str, Any] = {}
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

    async def post(
        self, url: str, json: Any | None = None, headers: dict[str, Any] | None = None, verify: bool | None = None
    ) -> httpx.Response:
        return await self._request(method="post", url=url, json=json, headers=headers, verify=verify)
