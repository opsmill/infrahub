from collections import defaultdict

from infrahub.database import InfrahubDatabase

from ..model.path import CalculatedDiffs, EnrichedDiffRoot
from ..payload_builder import get_display_labels
from .interface import DiffEnricherInterface


class DiffLabelsEnricher(DiffEnricherInterface):
    """Add display labels for nodes and labels for relationships"""

    def __init__(self, db: InfrahubDatabase):
        self.db = db

    async def enrich(self, enriched_diff_root: EnrichedDiffRoot, calculated_diffs: CalculatedDiffs) -> None:
        node_kind_map = defaultdict(list)
        diff_branch_name = enriched_diff_root.diff_branch_name
        for node in enriched_diff_root.nodes:
            node_kind_map[node.kind].append(node.uuid)
            if not node.relationships:
                continue
            node_schema = self.db.schema.get(name=node.kind, branch=diff_branch_name, duplicate=False)
            for relationship_diff in node.relationships:
                relationship_schema = node_schema.get_relationship(name=relationship_diff.name)
                relationship_diff.label = relationship_schema.label or ""
                peer_kind = relationship_schema.peer
                for element in relationship_diff.relationships:
                    node_kind_map[peer_kind].append(element.peer_id)

        display_label_map = await get_display_labels(
            db=self.db, nodes={diff_branch_name: node_kind_map}, ignore_deleted=False
        )
        for node in enriched_diff_root.nodes:
            try:
                display_label = display_label_map[diff_branch_name][node.uuid]
            except KeyError:
                display_label = None
            if display_label:
                node.label = display_label

            for relationship_diff in node.relationships:
                for element in relationship_diff.relationships:
                    try:
                        element.peer_label = display_label_map[diff_branch_name][element.peer_id]
                    except KeyError:
                        pass
