import asyncio
from typing import Any

import httpx
import ujson
from fastapi import FastAPI
from infrahub_sdk.types import HTTPMethod

from infrahub.core.registry import registry


async def dummy_async_request(
    url: str, method: HTTPMethod, headers: dict[str, Any], timeout: int, payload: dict | None = None
) -> httpx.Response:
    """Return an empty response and to pretend that the git commit was updated successfully."""
    return httpx.Response(status_code=200, json={"data": {}}, request=httpx.Request(method="POST", url="http://mock"))


async def registered_branches_async_request(
    url: str, method: HTTPMethod, headers: dict[str, Any], timeout: int, payload: dict | None = None
) -> httpx.Response:
    """Answer the branch listing with the branches of the registry, and every other request like the dummy requester."""
    if payload and "GetAllBranch" in payload.get("query", ""):
        data: dict[str, Any] = {
            "Branch": [
                {
                    "id": str(branch.uuid),
                    "name": name,
                    "sync_with_git": branch.sync_with_git,
                    "is_default": branch.is_default,
                    "has_schema_changes": False,
                    "branched_from": str(branch.branched_from),
                }
                for name, branch in registry.branch.items()
            ]
        }
    else:
        data = {}
    return httpx.Response(status_code=200, json={"data": data}, request=httpx.Request(method="POST", url="http://mock"))


REJECTED_REQUEST_MESSAGE = "The request was rejected"


async def rejected_async_request(
    url: str, method: HTTPMethod, headers: dict[str, Any], timeout: int, payload: dict | None = None
) -> httpx.Response:
    """Return a GraphQL error for every request, as the server does when it rejects a mutation."""
    return httpx.Response(
        status_code=200,
        json={"errors": [{"message": REJECTED_REQUEST_MESSAGE}]},
        request=httpx.Request(method="POST", url="http://mock"),
    )


class InfrahubTestClient(httpx.AsyncClient):
    def __init__(self, app: FastAPI, base_url: str = "") -> None:
        self.loop = asyncio.get_event_loop()
        super().__init__(transport=httpx.ASGITransport(app=app), base_url=base_url)

    async def _request(
        self, url: str, method: HTTPMethod, headers: dict[str, Any], timeout: int, payload: dict | None = None
    ) -> httpx.Response:
        content = None
        if payload:
            content = str(ujson.dumps(payload)).encode("UTF-8")
        return await self.request(method=method.value, url=url, headers=headers, timeout=timeout, content=content)

    async def async_request(
        self, url: str, method: HTTPMethod, headers: dict[str, Any], timeout: int, payload: dict | None = None
    ) -> httpx.Response:
        return await self._request(url=url, method=method, headers=headers, timeout=timeout, payload=payload)

    def sync_request(
        self, url: str, method: HTTPMethod, headers: dict[str, Any], timeout: int, payload: dict | None = None
    ) -> httpx.Response:
        future = asyncio.run_coroutine_threadsafe(
            self._request(url=url, method=method, headers=headers, timeout=timeout, payload=payload), self.loop
        )
        return future.result()
