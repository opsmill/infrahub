from typing import Protocol

from prefect.client.schemas.objects import FlowRun

from infrahub.core.query.node import NodeGetKindQuery
from infrahub.database import InfrahubDatabase

from .models import RelatedNodesInfo
from .tags import WorkflowTagDecoder


class RelatedNodeEnricherProtocol(Protocol):
    async def enrich(self, flows: list[FlowRun]) -> RelatedNodesInfo: ...


class RelatedNodeEnricher:
    """Resolve the nodes referenced by flow-run tags and attach their kind from the graph."""

    def __init__(self, db: InfrahubDatabase, tag_decoder: WorkflowTagDecoder) -> None:
        self.db = db
        self.tag_decoder = tag_decoder

    async def enrich(self, flows: list[FlowRun]) -> RelatedNodesInfo:
        related_nodes = RelatedNodesInfo()

        for flow in flows:
            related_node_ids = self.tag_decoder.related_node_ids(flow)
            if not related_node_ids:
                continue
            related_nodes.add_nodes(flow_id=flow.id, node_ids=related_node_ids)

        if unique_related_node_ids := related_nodes.get_unique_related_node_ids():
            query = await NodeGetKindQuery.init(db=self.db, ids=unique_related_node_ids)
            await query.execute(db=self.db)
            unique_related_node_ids_kind = await query.get_node_kind_map()

            for node_id, node_kind in unique_related_node_ids_kind.items():
                if node_id in related_nodes.nodes:
                    related_nodes.nodes[node_id].kind = node_kind

        return related_nodes
