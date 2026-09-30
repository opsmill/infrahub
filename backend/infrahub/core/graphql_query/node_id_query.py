from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar

from infrahub_sdk.graphql import Query
from pydantic import BaseModel

from infrahub.utilities.chunks import chunked

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from infrahub_sdk.client import InfrahubClient


class NodeIDQuery(BaseModel):
    """Base query that fetches only the `id` field for all nodes of a given kind."""

    query_name: ClassVar[str] = "FetchNodeIDs"
    kind: str

    def render_query(self) -> str:
        query = Query(
            name=self.query_name,
            variables={"offset": int | None, "limit": int | None},
            query={
                self.kind: {
                    "@filters": {"offset": "$offset", "limit": "$limit"},
                    "edges": {"node": {"id": None}},
                }
            },
        )
        return query.render()

    def parse_response(self, response: dict[str, Any]) -> list[str]:
        result: list[str] = []
        if kind_payload := response.get(self.kind):
            for edge in kind_payload.get("edges", []):
                if node := edge.get("node"):
                    if node_id := node.get("id"):
                        result.append(node_id)
        return result

    async def fetch_all_paginated(
        self, client: InfrahubClient, branch_name: str, page_size: int | None = None
    ) -> AsyncGenerator[list[str], None]:
        page_size = page_size or client.config.pagination_size
        rendered_query = self.render_query()
        offset = 0
        while True:
            response = await client.execute_graphql(
                query=rendered_query,
                variables={"offset": offset, "limit": page_size},
                branch_name=branch_name,
            )
            page = self.parse_response(response=response)
            yield page
            if len(page) < page_size:
                break
            offset += page_size

    async def fetch_all_chunked(
        self, client: InfrahubClient, branch_name: str, chunk_size: int
    ) -> AsyncGenerator[list[str], None]:
        """Yield every node id of the kind in chunks of at most ``chunk_size``.

        Pages are fetched at the client's pagination size, or at ``chunk_size`` when that is larger.

        Raises:
            ValueError: if ``chunk_size`` is not positive.

        """
        # Paging below the chunk size would cap every chunk at the page size.
        page_size = max(client.config.pagination_size, chunk_size)
        async for page in self.fetch_all_paginated(client=client, branch_name=branch_name, page_size=page_size):
            for chunk in chunked(page, chunk_size):
                yield chunk
