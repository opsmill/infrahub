from __future__ import annotations

import ssl
from typing import TYPE_CHECKING, Any

import httpx

from infrahub import config
from infrahub.exceptions import HTTPServerError, HTTPServerSSLError, HTTPServerTimeoutError
from infrahub.log import get_logger
from infrahub.services.adapters.http import InfrahubHTTP

if TYPE_CHECKING:
    from infrahub.tls.registry import TlsContextRegistry

log = get_logger()


class HttpxAdapter(InfrahubHTTP):
    """The HttpxAdapter is a generic interface for InfrahubHTTP

    The class provides a way to send HTTP requests from Infrahub for example
    when sending webhooks, telemetry data or when communicating with SSO
    providers. The main purpose is to have a single location to manage
    configuration and error handling with regards to HTTP traffic and
    allow users to define configurations such as timeout, TLS options
    and eventually proxy settings in one location."""

    def __init__(self, tls_registry: TlsContextRegistry) -> None:
        self._tls_registry = tls_registry
        self._settings: config.HTTPSettings | None = None

    @property
    def settings(self) -> config.HTTPSettings:
        if self._settings:
            return self._settings

        self._settings = config.SETTINGS.http
        return self._settings

    def verify_tls(self, verify: bool | None = None) -> bool | ssl.SSLContext:
        """Determine the TLS verification behavior for a request.

        Args:
            verify: Override for TLS verification behavior.
                - None: Use global settings (may skip verification if tls_insecure=True)
                - False: Explicitly disable certificate validation
                - True: Force certificate validation, ignoring global tls_insecure setting

        Returns:
            False to disable verification, or an SSLContext for verification.
        """
        if verify is False:
            return False
        if verify is True:
            return self._tls_registry.get(
                insecure=self.settings.tls_insecure, ca_bundle=self.settings.tls_ca_bundle, force_verify=True
            )

        return self._tls_registry.get(insecure=self.settings.tls_insecure, ca_bundle=self.settings.tls_ca_bundle)

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
                log.info(f"TLS verification failed for connection to {url}")
                raise HTTPServerSSLError(message=f"Unable to validate TLS certificate for connection to {url}") from exc
            except httpx.ReadTimeout as exc:
                log.info(f"Connection timed out when trying to reach {url}")
                raise HTTPServerTimeoutError(
                    message=f"Connection to {url} timed out after {self.settings.timeout}"
                ) from exc
            except httpx.RequestError as exc:
                # Catch all error from httpx
                log.warning(f"Unhandled HTTP error for {url} ({exc})")
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
