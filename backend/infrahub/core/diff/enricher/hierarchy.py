from collections import defaultdict

from infrahub.core import registry
from infrahub.core.constants import RelationshipHierarchyDirection, RelationshipKind
from infrahub.core.constants.database import DatabaseEdgeType
from infrahub.core.query.node import NodeGetHierarchyQuery
from infrahub.core.query.relationship import RelationshipGetPeerQuery, RelationshipPeerData
from infrahub.core.schema import ProfileSchema, TemplateSchema
from infrahub.database import InfrahubDatabase
from infrahub.log import get_logger

from ..model.path import (
    CalculatedDiffs,
    EnrichedDiffRoot,
)
from ..parent_node_adder import DiffParentNodeAdder, ParentNodeAddRequest
from .interface import DiffEnricherInterface

log = get_logger()


class DiffHierarchyEnricher(DiffEnricherInterface):
    """Add hierarchy and parent/component nodes to diff even if the higher-level nodes are unchanged"""

    def __init__(self, db: InfrahubDatabase, parent_adder: DiffParentNodeAdder):
        self.db = db
        self.parent_adder = parent_adder

    async def enrich(
        self,
        enriched_diff_root: EnrichedDiffRoot,
        calculated_diffs: CalculatedDiffs | None = None,  # noqa: ARG002
    ) -> None:
        # A hierarchy can be defined in 2 ways
        # - A node has a relationship of kind parent
        # - A node is part of a hierarchy

        log.info("Beginning hierarchical diff enrichment...")
        self.parent_adder.initialize(enriched_diff_root=enriched_diff_root)
        node_rel_parent_map: dict[str, list[str]] = defaultdict(list)
        node_hierarchy_map: dict[str, list[str]] = defaultdict(list)

        for node in enriched_diff_root.nodes:
            schema_node = self.db.schema.get(
                name=node.kind, branch=enriched_diff_root.diff_branch_name, duplicate=False
            )

            if isinstance(schema_node, ProfileSchema | TemplateSchema):
                continue

            if schema_node.has_parent_relationship:
                node_rel_parent_map[node.kind].append(node.uuid)
                continue

            try:
                hierarchy_schema = schema_node.get_hierarchy_schema(
                    db=self.db, branch=enriched_diff_root.diff_branch_name
                )
                node_hierarchy_map[hierarchy_schema.kind].append(node.uuid)
            except ValueError:
                pass

        await self._enrich_nodes_with_parent(enriched_diff_root=enriched_diff_root, node_map=node_rel_parent_map)
        await self._enrich_hierarchical_nodes(enriched_diff_root=enriched_diff_root, node_map=node_hierarchy_map)
        log.info("Hierarchical diff enrichment complete.")

    async def _enrich_hierarchical_nodes(
        self,
        enriched_diff_root: EnrichedDiffRoot,
        node_map: dict[str, list[str]],
    ) -> None:
        diff_branch = registry.get_branch_from_registry(branch=enriched_diff_root.diff_branch_name)

        # Retrieve the ID of all ancestors
        for kind, node_ids in node_map.items():
            log.info(f"Beginning hierarchy enrichment for {kind} node, num_nodes={len(node_ids)}...")
            hierarchy_schema = self.db.schema.get(
                name=kind, branch=enriched_diff_root.diff_branch_name, duplicate=False
            )
            for node_id in node_ids:
                query = await NodeGetHierarchyQuery.init(
                    db=self.db,
                    direction=RelationshipHierarchyDirection.ANCESTORS,
                    node_id=node_id,
                    node_schema=hierarchy_schema,
                    branch=diff_branch,
                    hierarchical_ordering=True,
                )
                await query.execute(db=self.db)

                ancestors = list(query.get_relatives())

                if not ancestors:
                    continue

                node = enriched_diff_root.get_node(node_uuid=node_id)
                parent_rel = hierarchy_schema.get_relationship(name="parent")

                current_node = node
                for ancestor in ancestors:
                    parent_request = ParentNodeAddRequest(
                        node_id=current_node.uuid,
                        parent_id=str(ancestor.uuid),
                        parent_kind=ancestor.kind,
                        parent_label="",
                        parent_rel_name=parent_rel.name,
                        parent_rel_identifier=parent_rel.get_identifier(),
                        parent_rel_cardinality=parent_rel.cardinality,
                        parent_rel_label=parent_rel.label or "",
                    )
                    parent = self.parent_adder.add_parent(parent_request=parent_request)

                    current_node = parent

    async def _enrich_nodes_with_parent(
        self, enriched_diff_root: EnrichedDiffRoot, node_map: dict[str, list[str]]
    ) -> None:
        diff_branch = registry.get_branch_from_registry(branch=enriched_diff_root.diff_branch_name)

        parent_peers: dict[str, RelationshipPeerData] = {}

        # Prepare a map to capture all parents that also have a parent
        node_parent_with_parent_map: dict[str, list[str]] = defaultdict(list)

        # TODO Not gonna implement it now but technically we could check the content of the node to see if the parent relationship is present

        # Query the UUID of the parent
        for kind, ids in node_map.items():
            log.info(f"Beginning parent enrichment for {kind} node, num_nodes={len(ids)}...")
            schema_node = self.db.schema.get(name=kind, branch=enriched_diff_root.diff_branch_name, duplicate=False)

            parent_rel = [rel for rel in schema_node.relationships if rel.kind == RelationshipKind.PARENT][0]
            parent_schema = self.db.schema.get(
                name=parent_rel.peer, branch=enriched_diff_root.diff_branch_name, duplicate=False
            )

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
                if parent_schema.has_parent_relationship:
                    node_parent_with_parent_map[parent_schema.kind].append(str(peer.peer_id))

        # Check if the parent are already present
        # If parent is already in the list of node we need to add a relationship
        # If parent is not in the list of node, we need to add it
        diff_node_map = enriched_diff_root.get_node_map(node_uuids=set(parent_peers.keys()))
        for node_id, peer_parent in parent_peers.items():
            # TODO check if we can optimize this part to avoid querying this multiple times
            node = diff_node_map[node_id]
            schema_node = self.db.schema.get(
                name=node.kind, branch=enriched_diff_root.diff_branch_name, duplicate=False
            )
            parent_rel = [rel for rel in schema_node.relationships if rel.kind == RelationshipKind.PARENT][0]

            parent_request = ParentNodeAddRequest(
                node_id=node.uuid,
                parent_id=str(peer_parent.peer_id),
                parent_kind=peer_parent.peer_kind,
                parent_label="",
                parent_rel_name=parent_rel.name,
                parent_rel_identifier=parent_rel.get_identifier(),
                parent_rel_cardinality=parent_rel.cardinality,
                parent_rel_label=parent_rel.label or "",
            )
            self.parent_adder.add_parent(parent_request=parent_request)

        if node_parent_with_parent_map:
            await self._enrich_nodes_with_parent(
                enriched_diff_root=enriched_diff_root, node_map=node_parent_with_parent_map
            )
