from collections import defaultdict

from infrahub.core import registry
from infrahub.core.constants import RelationshipKind
from infrahub.core.constants.database import DatabaseEdgeType
from infrahub.core.query.relationship import RelationshipGetPeerQuery, RelationshipPeerData
from infrahub.core.schema import ProfileSchema
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase

from ..model.path import (
    CalculatedDiffs,
    DiffAction,
    EnrichedDiffNode,
    EnrichedDiffRelationship,
    EnrichedDiffRoot,
)
from .interface import DiffEnricherInterface


class DiffHierarchyEnricher(DiffEnricherInterface):
    """Add hierarchy and parent/component nodes to diff even if the higher-level nodes are unchanged"""

    def __init__(self, db: InfrahubDatabase):
        self.db = db

    async def enrich(
        self, enriched_diff_root: EnrichedDiffRoot, calculated_diffs: CalculatedDiffs | None = None
    ) -> None:
        # A hierarchy can be defined in 2 ways
        # - A node has a relationship of kind parent
        # - A node is part of a hierarchy

        node_rel_parent_map = defaultdict(list)
        # node_hierarchy_map = defaultdict(list)

        for node in enriched_diff_root.nodes:
            schema_node = self.db.schema.get(
                name=node.kind, branch=enriched_diff_root.diff_branch_name, duplicate=False
            )

            if isinstance(schema_node, ProfileSchema):
                continue

            if schema_node.has_parent_relationship:
                node_rel_parent_map[node.kind].append(node.uuid)

            # elif schema_node.get_hierarchy_schema(db=self.db, branch=enriched_diff_root.diff_branch_name):
            #     node_hierarchy_map[node.kind].append(node.uuid)

        await self._enrich_nodes_with_parent(enriched_diff_root=enriched_diff_root, node_map=node_rel_parent_map)
        # await self._enrich_hierachical_nodes(enriched_diff_root=enriched_diff_root, node_map=node_hierarchy_map)

    # pylint: disable=unused-argument
    async def _enrich_hierachical_nodes(
        self,
        enriched_diff_root: EnrichedDiffRoot,
        node_map: dict[str, list[str]],
    ) -> None: ...

    async def _enrich_nodes_with_parent(
        self, enriched_diff_root: EnrichedDiffRoot, node_map: dict[str, list[str]]
    ) -> None:
        diff_branch = registry.get_branch_from_registry(branch=enriched_diff_root.diff_branch_name)

        parent_peers: dict[str, RelationshipPeerData] = {}

        # Query the UUID of the parent
        for kind, ids in node_map.items():
            schema_node = self.db.schema.get(name=kind, branch=enriched_diff_root.diff_branch_name, duplicate=False)

            parent_rel = [rel for rel in schema_node.relationships if rel.kind == RelationshipKind.PARENT][0]

            # TODO Not gonna implement it now but technically we could check the content of the node to see if the parent relationship is present

            query = await RelationshipGetPeerQuery.init(
                db=self.db,
                branch=diff_branch,
                source_ids=ids,
                rel_type=DatabaseEdgeType.IS_RELATED.value,
                schema=parent_rel,
            )
            await query.execute(db=self.db)

            for peer in query.get_peers():
                parent_peers[str(peer.source_id)] = peer

        # Check if the parent are already present
        # If parent is already in the list of node we need to add a relationship
        # If parent is not in the list of node, we need to add it
        for node_id, peer_parent in parent_peers.items():
            # TODO check if we can optimize this part to avoid querying this multiple times
            node = enriched_diff_root.get_node(node_uuid=node_id)
            schema_node = self.db.schema.get(
                name=node.kind, branch=enriched_diff_root.diff_branch_name, duplicate=False
            )
            parent_rel = [rel for rel in schema_node.relationships if rel.kind == RelationshipKind.PARENT][0]

            if not enriched_diff_root.has_node(node_uuid=str(peer_parent.peer_id)):
                schema_parent = self.db.schema.get(
                    name=peer_parent.peer_kind, branch=enriched_diff_root.diff_branch_name, duplicate=False
                )
                parent_side_rel = schema_parent.get_relationship_by_identifier(
                    id=parent_rel.get_identifier(), raise_on_error=False
                )

                parent = EnrichedDiffNode(
                    uuid=str(peer_parent.peer_id),
                    kind=peer_parent.peer_kind,
                    label="",
                    action=DiffAction.UNCHANGED,
                    changed_at=Timestamp(),
                )

                if parent_side_rel:
                    parent.relationships.add(
                        EnrichedDiffRelationship(
                            name=parent_side_rel.name,
                            label=parent_side_rel.label or "",
                            changed_at=Timestamp(),
                            action=DiffAction.UNCHANGED,
                            nodes={node},
                        )
                    )

                enriched_diff_root.nodes.add(parent)

            else:
                parent = enriched_diff_root.get_node(node_uuid=str(peer_parent.peer_id))

            # Add the relationship to the parent
            if node.has_relationship(name=parent_rel.name):
                rel = node.get_relationship(name=parent_rel.name)
                if not rel.nodes:
                    rel.nodes.add(parent)
            else:
                node.relationships.add(
                    EnrichedDiffRelationship(
                        name=parent_rel.name,
                        label=parent_rel.label or "",
                        changed_at=Timestamp(),
                        action=DiffAction.UNCHANGED,
                        nodes={parent},
                    )
                )
