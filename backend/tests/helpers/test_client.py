import asyncio
import json
from typing import Any, Dict, Optional

import httpx
from fastapi import FastAPI
from infrahub_sdk.types import HTTPMethod


class InfrahubTestClient(httpx.AsyncClient):
    def __init__(self, app: FastAPI, base_url: str = ""):
        self.loop = asyncio.get_event_loop()
        super().__init__(app=app, base_url=base_url)

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

    def sync_request(
        self, url: str, method: HTTPMethod, headers: Dict[str, Any], timeout: int, payload: Optional[Dict] = None
    ) -> httpx.Response:
        future = asyncio.run_coroutine_threadsafe(
            self._request(url=url, method=method, headers=headers, timeout=timeout, payload=payload), self.loop
        )
        return future.result()
