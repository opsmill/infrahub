import json
from typing import Any, Dict, Optional

import httpx
from infrahub_sdk.types import HTTPMethod


class InfrahubTestClient(httpx.AsyncClient):
    async def _request(
        self, url: str, method: HTTPMethod, headers: Dict[str, Any], timeout: int, payload: Optional[Dict] = None
    ) -> httpx.Response:
        content = None
        if payload:
            content = str(json.dumps(payload)).encode("UTF-8")
        return await self.request(method=method.value, url=url, headers=headers, timeout=timeout, content=content)

    async def async_request(
        self, url: str, method: HTTPMethod, headers: Dict[str, Any], timeout: int, payload: Optional[Dict] = None
    ) -> httpx.Response:
        return await self._request(url=url, method=method, headers=headers, timeout=timeout, payload=payload)
