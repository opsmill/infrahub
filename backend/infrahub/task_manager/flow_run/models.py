from collections import defaultdict
from uuid import UUID

from prefect.client.schemas.objects import FlowRun, StateType
from prefect.client.schemas.objects import Log as PrefectLog
from pydantic import BaseModel, Field


class RelatedNodeInfo(BaseModel):
    id: str
    kind: str | None = None


class RelatedNodesInfo(BaseModel):
    flows: dict[UUID, dict[str, RelatedNodeInfo]] = Field(default_factory=lambda: defaultdict(dict))  # type: ignore[arg-type]
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
    logs: defaultdict[UUID, list[PrefectLog]] = Field(default_factory=lambda: defaultdict(list))  # type: ignore[arg-type]


class FlowProgress(BaseModel):
    data: dict[UUID, float] = Field(default_factory=dict)


class FlowRunQueryCriteria(BaseModel):
    """Transport-agnostic description of which flow runs to select."""

    q: str | None = None
    ids: list[str] | None = None
    related_nodes: list[str] | None = None
    statuses: list[StateType] | None = None
    workflows: list[str] | None = None
    tags: list[str] | None = None
    branch: str | None = None
    limit: int | None = None
    offset: int | None = None


class FlowRunFetchOptions(BaseModel):
    """Explicit selection of which data to gather, decoupled from any GraphQL selection set."""

    include_count: bool = False
    include_runs: bool = False
    include_logs: bool = False
    include_progress: bool = False
    include_related_nodes: bool = False
    include_workflow: bool = False
    log_limit: int | None = None
    log_offset: int | None = None


class EnrichedFlowRun(BaseModel):
    model_config = {"arbitrary_types_allowed": True}

    flow_run: FlowRun
    branch: str | None = None
    related_nodes: list[RelatedNodeInfo] = Field(default_factory=list)
    workflow_name: str | None = None
    progress: float | None = None
    logs: list[PrefectLog] = Field(default_factory=list)


class FlowRunQueryResult(BaseModel):
    count: int = 0
    runs: list[EnrichedFlowRun] = Field(default_factory=list)
