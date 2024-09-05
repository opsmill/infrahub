from __future__ import annotations

from typing import Any

import httpx

from infrahub.services.adapters.http import InfrahubHTTP


class HttpxAdapter(InfrahubHTTP):
    async def post(
        self, url: str, json: Any | None = None, headers: dict[str, Any] | None = None, verify: bool | None = None
    ) -> None:
        # Later verify will be controlled by the base settings for the HTTP adapter instead of defaulting
        # to True
        verify = verify if verify is not None else True
        headers = headers or {}
        async with httpx.AsyncClient(verify=verify) as client:
            await client.post(url=url, json=json, headers=headers)
