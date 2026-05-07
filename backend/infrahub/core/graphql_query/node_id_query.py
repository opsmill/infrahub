from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar

from infrahub_sdk.graphql import Query
from pydantic import BaseModel, ConfigDict

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from infrahub_sdk.client import InfrahubClient

PAGE_SIZE = 50


class NodeID(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str


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

    def parse_response(self, response: dict[str, Any]) -> list[NodeID]:
        result: list[NodeID] = []
        if kind_payload := response.get(self.kind):
            for edge in kind_payload.get("edges", []):
                if node := edge.get("node"):
                    if node_id := node.get("id"):
                        result.append(NodeID(id=node_id))
        return result

    async def fetch_all_paginated(
        self, client: InfrahubClient, branch_name: str, page_size: int = PAGE_SIZE
    ) -> AsyncGenerator[list[NodeID], None]:
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
