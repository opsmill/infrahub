from __future__ import annotations

import copy
from typing import TYPE_CHECKING, Optional

import httpx

from infrahub_sdk.exceptions import AuthenticationError, ServerNotReachableError

if TYPE_CHECKING:
    from infrahub_sdk.client import InfrahubClient, InfrahubClientSync


class ObjectStoreBase:
    pass


class ObjectStore(ObjectStoreBase):
    def __init__(self, client: InfrahubClient):
        self.client = client

    async def get(self, identifier: str, tracker: Optional[str] = None) -> str:
        url = f"{self.client.address}/api/storage/object/{identifier}"
        headers = copy.copy(self.client.headers or {})
        if self.client.insert_tracker and tracker:
            headers["X-Infrahub-Tracker"] = tracker

        try:
            resp = await self.client._get(url=url, headers=headers)
            resp.raise_for_status()

        except ServerNotReachableError:
            self.client.log.error(f"Unable to connect to {self.client.address} .. ")
            raise
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in [401, 403]:
                response = exc.response.json()
                errors = response.get("errors")
                messages = [error.get("message") for error in errors]
                raise AuthenticationError(" | ".join(messages)) from exc

        return resp.text

    async def upload(self, content: str, tracker: Optional[str] = None) -> dict[str, str]:
        url = f"{self.client.address}/api/storage/upload/content"
        headers = copy.copy(self.client.headers or {})
        if self.client.insert_tracker and tracker:
            headers["X-Infrahub-Tracker"] = tracker

        try:
            resp = await self.client._post(url=url, payload={"content": content}, headers=headers)
            resp.raise_for_status()
        except ServerNotReachableError:
            self.client.log.error(f"Unable to connect to {self.client.address} .. ")
            raise
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in [401, 403]:
                response = exc.response.json()
                errors = response.get("errors")
                messages = [error.get("message") for error in errors]
                raise AuthenticationError(" | ".join(messages)) from exc

        return resp.json()


class ObjectStoreSync(ObjectStoreBase):
    def __init__(self, client: InfrahubClientSync):
        self.client = client

    def get(self, identifier: str, tracker: Optional[str] = None) -> str:
        url = f"{self.client.address}/api/storage/object/{identifier}"
        headers = copy.copy(self.client.headers or {})
        if self.client.insert_tracker and tracker:
            headers["X-Infrahub-Tracker"] = tracker

        try:
            resp = self.client._get(url=url, headers=headers)
            resp.raise_for_status()

        except ServerNotReachableError:
            self.client.log.error(f"Unable to connect to {self.client.address} .. ")
            raise
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in [401, 403]:
                response = exc.response.json()
                errors = response.get("errors")
                messages = [error.get("message") for error in errors]
                raise AuthenticationError(" | ".join(messages)) from exc

        return resp.text

    def upload(self, content: str, tracker: Optional[str] = None) -> dict[str, str]:
        url = f"{self.client.address}/api/storage/upload/content"
        headers = copy.copy(self.client.headers or {})
        if self.client.insert_tracker and tracker:
            headers["X-Infrahub-Tracker"] = tracker

        try:
            resp = self.client._post(url=url, payload={"content": content}, headers=headers)
            resp.raise_for_status()
        except ServerNotReachableError:
            self.client.log.error(f"Unable to connect to {self.client.address} .. ")
            raise
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in [401, 403]:
                response = exc.response.json()
                errors = response.get("errors")
                messages = [error.get("message") for error in errors]
                raise AuthenticationError(" | ".join(messages)) from exc

        return resp.json()
