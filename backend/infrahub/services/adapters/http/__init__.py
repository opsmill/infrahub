from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import httpx

    from infrahub.services import InfrahubServices


class InfrahubHTTP:
    async def initialize(self, service: InfrahubServices) -> None:
        """Initialize the HTTP adapter"""

    async def post(
        self, url: str, json: Any | None = None, headers: dict[str, Any] | None = None, verify: bool | None = None
    ) -> httpx.Response:
        raise NotImplementedError()
