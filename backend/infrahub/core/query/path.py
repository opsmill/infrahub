from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from infrahub.core.query import Query, QueryType

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase


@dataclass(frozen=True)
class PathNodeData:
    uuid: str
    kind: str
    display_label: str
    db_id: str


@dataclass(frozen=True)
class PathRelationshipData:
    uuid: str
    name: str
    direction: str


@dataclass(frozen=True)
class PathData:
    nodes: list[PathNodeData]
    relationships: list[PathRelationshipData]
    depth: int


# Namespaces excluded from traversal by default.
# These contain internal/system nodes that add noise to path results.
DEFAULT_EXCLUDED_NAMESPACES = (
    "Core",
    "Internal",
    "Builtin",
    "Lineage",
    "Profile",
    "Template",
)


class PathTraversalQuery(Query):
    name = "path_traversal"
    type = QueryType.READ
    insert_return = False
    insert_limit = False

    def __init__(
        self,
        source_id: str,
        destination_id: str,
        max_depth: int = 5,
        max_paths: int = 10,
        node_filter: list[str] | None = None,
        relationship_filter: list[str] | None = None,
        excluded_namespaces: list[str] | None = None,
        excluded_kinds: list[str] | None = None,
        **kwargs: Any,
    ) -> None:
        if source_id == destination_id:
            raise ValueError("Source and destination nodes must be different")
        if not 1 <= max_depth <= 20:
            raise ValueError("max_depth must be between 1 and 20")
        if not 1 <= max_paths <= 100:
            raise ValueError("max_paths must be between 1 and 100")

        self.source_id = source_id
        self.destination_id = destination_id
        self.max_depth = max_depth
        self.max_paths = max_paths
        self.node_filter = node_filter or []
        self.relationship_filter = relationship_filter or []
        self.excluded_namespaces = (
            excluded_namespaces if excluded_namespaces is not None else list(DEFAULT_EXCLUDED_NAMESPACES)
        )
        self.excluded_kinds = excluded_kinds or []

        super().__init__(**kwargs)

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        branch_filter, branch_params = self.branch.get_query_filter_path(at=self.at.to_string())
        self.params.update(branch_params)
        self.params["source_uuid"] = self.source_id
        self.params["target_uuid"] = self.destination_id

        # Each user-visible hop is 2 edges (Node->IS_RELATED->Relationship->IS_RELATED->Node)
        max_edge_length = self.max_depth * 2

        # Build WHERE clauses for path filtering
        # Use branch_filter broadly to find candidate paths, then validate
        # each edge individually using the latest-edge pattern.
        where_clauses = [
            f"all(r IN relationships(path) WHERE ({branch_filter}))",
        ]

        # Namespace exclusion: skip intermediate nodes from system namespaces
        # Source and target are always allowed through; Relationship vertices are skipped.
        if self.excluded_namespaces:
            self.params["excluded_namespaces"] = self.excluded_namespaces
            where_clauses.append(
                "all(n IN nodes(path) WHERE "
                "n.uuid IN [$source_uuid, $target_uuid] "
                "OR NOT n:Node "  # Allow Relationship vertices through
                "OR NOT n.namespace IN $excluded_namespaces)"
            )

        # Kind exclusion: skip specific kinds from the path
        if self.excluded_kinds:
            self.params["excluded_kinds"] = self.excluded_kinds
            where_clauses.append(
                "all(n IN nodes(path) WHERE "
                "n.uuid IN [$source_uuid, $target_uuid] "
                "OR NOT n:Node "
                "OR NOT n.kind IN $excluded_kinds)"
            )

        # Node kind filter: allow source/target to be any kind, filter intermediates
        if self.node_filter:
            self.params["node_filter"] = self.node_filter
            where_clauses.append(
                "all(n IN nodes(path) WHERE "
                "n.uuid IN [$source_uuid, $target_uuid] "
                "OR NOT n:Node "  # Allow Relationship vertices through
                "OR n.kind IN $node_filter)"
            )

        # Relationship name filter: filter on the Relationship vertex name property
        if self.relationship_filter:
            self.params["relationship_filter"] = self.relationship_filter
            where_clauses.append(
                "all(n IN nodes(path) WHERE "
                "NOT n:Relationship "  # Skip Node vertices for this check
                "OR n.name IN $relationship_filter)"
            )

        where_str = " AND ".join(where_clauses)

        if self.branch.is_default:
            # On the default branch, there are no branch-deleted edges to worry
            # about. We can filter directly for active status, which is much faster.
            query = f"""
            MATCH (source:Node {{ uuid: $source_uuid }}), (target:Node {{ uuid: $target_uuid }})
            MATCH path = (source)-[:IS_RELATED*2..{max_edge_length}]-(target)
            WHERE {where_str}
            AND all(r IN relationships(path) WHERE r.status = "active")
            RETURN path, length(path) AS path_length
            ORDER BY path_length ASC
            LIMIT {self.max_paths}
            """
        else:
            # On non-default branches, an edge might be active on the default
            # branch but deleted on this branch. We need to check each edge's
            # latest version (highest branch_level, most recent from) and only
            # keep paths where all edges are active at that version.
            #
            # Pattern from attribute.py:
            #   CALL (a, np) {
            #       MATCH (a)-[r:REL]->(np) WHERE branch_filter
            #       ORDER BY r.branch_level DESC, r.from DESC, r.status ASC
            #       LIMIT 1
            #       RETURN r
            #   }
            #   WHERE r.status = "active"
            #
            # First find a limited set of candidate paths, then validate edges:
            query = f"""
            MATCH (source:Node {{ uuid: $source_uuid }}), (target:Node {{ uuid: $target_uuid }})
            MATCH path = (source)-[:IS_RELATED*2..{max_edge_length}]-(target)
            WHERE {where_str}
            WITH path, length(path) AS path_length
            ORDER BY path_length ASC
            LIMIT {self.max_paths * 5}
            WITH path, path_length, relationships(path) AS rels
            UNWIND range(0, size(rels) - 1) AS idx
            WITH path, path_length, startNode(rels[idx]) AS sn, endNode(rels[idx]) AS en
            CALL (sn, en) {{
                MATCH (sn)-[r:IS_RELATED]-(en)
                WHERE ({branch_filter})
                RETURN r
                ORDER BY r.branch_level DESC, r.from DESC, r.status ASC
                LIMIT 1
            }}
            WITH path, path_length, r.status = "active" AS edge_active
            WITH path, path_length, collect(edge_active) AS edge_statuses
            WHERE ALL(s IN edge_statuses WHERE s = true)
            RETURN DISTINCT path, path_length
            ORDER BY path_length ASC
            LIMIT {self.max_paths}
            """

        self.add_to_query(query)
        self.return_labels = ["path", "length(path) AS path_length"]

    def get_paths(self) -> list[PathData]:
        """Extract typed path data from query results."""
        paths: list[PathData] = []

        for result in self.get_results():
            path = result.get_path(label="path")
            if path is None:
                continue

            raw_nodes = list(path.nodes)
            raw_rels = list(path.relationships)

            # Extract Node vertices (skip Relationship vertices at odd indices)
            # Path structure: Node, Rel-vertex, Node, Rel-vertex, Node, ...
            path_nodes: list[PathNodeData] = []
            path_relationships: list[PathRelationshipData] = []

            for i, node in enumerate(raw_nodes):
                if i % 2 == 0:
                    # This is an actual Node vertex
                    path_nodes.append(
                        PathNodeData(
                            uuid=node.get("uuid", ""),
                            kind=node.get("kind", ""),
                            display_label=node.get("display_label", node.get("kind", "")),
                            db_id=str(node.element_id) if hasattr(node, "element_id") else "",
                        )
                    )
                else:
                    # This is a Relationship vertex (intermediate)
                    # Determine direction based on the edges around this vertex
                    direction = "outbound"
                    if i < len(raw_rels):
                        rel = raw_rels[i - 1] if i > 0 else None
                        if rel and hasattr(rel, "start_node") and rel.start_node != raw_nodes[i - 1].element_id:
                            direction = "inbound"

                    path_relationships.append(
                        PathRelationshipData(
                            uuid=node.get("uuid", ""),
                            name=node.get("name", ""),
                            direction=direction,
                        )
                    )

            depth = len(path_nodes) - 1 if len(path_nodes) > 1 else 0

            paths.append(
                PathData(
                    nodes=path_nodes,
                    relationships=path_relationships,
                    depth=depth,
                )
            )

        return paths
