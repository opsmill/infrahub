from collections import defaultdict
from uuid import UUID

from prefect.client.schemas.objects import Log as PrefectLog
from pydantic import BaseModel, Field

from .constants import LOG_LEVEL_MAPPING


class RelatedNodeInfo(BaseModel):
    id: str
    kind: str | None = None


class RelatedNodesInfo(BaseModel):
    flows: dict[UUID, dict[str, RelatedNodeInfo]] = Field(default_factory=lambda: defaultdict(dict))
    nodes: dict[str, RelatedNodeInfo] = Field(default_factory=dict)

    def add_nodes(self, flow_id: UUID, node_ids: list[str]) -> None:
        for node_id in node_ids:
            self.add_node(flow_id=flow_id, node_id=node_id)

    def add_node(self, flow_id: UUID, node_id: str) -> None:
        if node_id not in self.nodes:
            node = RelatedNodeInfo(id=node_id)
            self.nodes[node_id] = node
        self.flows[flow_id][node_id] = self.nodes[node_id]

    def get_related_nodes(self, flow_id: UUID) -> list[RelatedNodeInfo]:
        if flow_id not in self.flows or len(self.flows[flow_id].keys()) == 0:
            return []
        return list(self.flows[flow_id].values())

    def get_related_nodes_as_dict(self, flow_id: UUID) -> list[dict[str, str | None]]:
        if flow_id not in self.flows or len(self.flows[flow_id].keys()) == 0:
            return []
        return [item.model_dump() for item in list(self.flows[flow_id].values())]

    def get_first_related_node(self, flow_id: UUID) -> RelatedNodeInfo | None:
        if nodes := self.get_related_nodes(flow_id=flow_id):
            return nodes[0]
        return None

    def get_unique_related_node_ids(self) -> list[str]:
        return list(self.nodes.keys())


class FlowLogs(BaseModel):
    logs: defaultdict[UUID, list[PrefectLog]] = Field(default_factory=lambda: defaultdict(list))

    def to_graphql(self, flow_id: UUID) -> list[dict]:
        return [
            {
                "node": {
                    "message": log.message,
                    "severity": LOG_LEVEL_MAPPING.get(log.level, "error"),
                    "timestamp": log.timestamp.to_iso8601_string(),
                }
            }
            for log in self.logs[flow_id]
        ]


class FlowProgress(BaseModel):
    data: dict[UUID, float] = Field(default_factory=dict)
