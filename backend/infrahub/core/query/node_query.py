from __future__ import annotations

from typing import Any, ClassVar

from infrahub_sdk.graphql import Query
from pydantic import BaseModel, ConfigDict


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
            query={self.kind: {"edges": {"node": {"id": None}}}},
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
