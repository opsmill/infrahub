from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from infrahub.core.query import Query, QueryType
from infrahub.core.query.path import DEFAULT_EXCLUDED_NAMESPACES, PathData, PathNodeData, PathRelationshipData

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase


@dataclass(frozen=True)
class DependencyNodeData:
    uuid: str
    kind: str
    display_label: str
    depth: int
    relationship_name: str
    path: PathData  # full path from source to this node


class DependencyQuery(Query):
    name = "dependency_discovery"
    type = QueryType.READ
    insert_return = False
    insert_limit = False

    def __init__(
        self,
        source_id: str,
        target_kinds: list[str],
        max_depth: int = 5,
        max_results: int = 50,
        excluded_namespaces: list[str] | None = None,
        **kwargs: Any,
    ) -> None:
        if not target_kinds:
            raise ValueError("At least one target kind is required")
        if not 1 <= max_depth <= 20:
            raise ValueError("max_depth must be between 1 and 20")
        if not 1 <= max_results <= 200:
            raise ValueError("max_results must be between 1 and 200")

        self.source_id = source_id
        self.target_kinds = target_kinds
        self.max_depth = max_depth
        self.max_results = max_results
        self.excluded_namespaces = (
            excluded_namespaces if excluded_namespaces is not None else list(DEFAULT_EXCLUDED_NAMESPACES)
        )
        super().__init__(**kwargs)

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        branch_filter, branch_params = self.branch.get_query_filter_path(at=self.at.to_string())
        self.params.update(branch_params)
        self.params["source_uuid"] = self.source_id
        self.params["target_kinds"] = self.target_kinds

        max_edge_length = self.max_depth * 2

        # Build namespace exclusion for intermediate nodes
        namespace_filter = ""
        if self.excluded_namespaces:
            self.params["excluded_namespaces"] = self.excluded_namespaces
            namespace_filter = (
                "AND all(n IN nodes(path) WHERE "
                "n.uuid = $source_uuid "
                "OR NOT n:Node "
                "OR n.kind IN $target_kinds "
                "OR NOT n.namespace IN $excluded_namespaces) "
            )

        # Find all reachable nodes of the target kinds, returning the shortest
        # path to each so the frontend can render the graph.
        query = f"""
        MATCH (source:Node {{ uuid: $source_uuid }})
        MATCH path = (source)-[:IS_RELATED*2..{max_edge_length}]-(target:Node)
        WHERE target.kind IN $target_kinds
        AND target.uuid <> $source_uuid
        AND all(r IN relationships(path) WHERE ({branch_filter}))
        {namespace_filter}
        WITH DISTINCT target, path, length(path) / 2 AS depth
        ORDER BY depth ASC
        WITH target, collect(path)[0] AS shortest_path, min(depth) AS min_depth
        RETURN target, shortest_path, min_depth
        ORDER BY min_depth ASC
        LIMIT {self.max_results}
        """

        self.add_to_query(query)
        self.return_labels = ["target", "shortest_path", "min_depth"]

    @staticmethod
    def _extract_path(path_obj: Any) -> PathData:
        """Extract PathData from a Neo4j path, reusing the same logic as PathTraversalQuery."""
        raw_nodes = list(path_obj.nodes)
        raw_rels = list(path_obj.relationships)

        path_nodes: list[PathNodeData] = []
        path_relationships: list[PathRelationshipData] = []

        for i, node in enumerate(raw_nodes):
            if i % 2 == 0:
                path_nodes.append(
                    PathNodeData(
                        uuid=node.get("uuid", ""),
                        kind=node.get("kind", ""),
                        display_label=node.get("display_label", node.get("kind", "")),
                        db_id=str(node.element_id) if hasattr(node, "element_id") else "",
                    )
                )
            else:
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
        return PathData(nodes=path_nodes, relationships=path_relationships, depth=depth)

    def get_dependency_nodes(self) -> list[DependencyNodeData]:
        results: list[DependencyNodeData] = []
        for result in self.get_results():
            target = result.get(label="target")
            depth = result.get(label="min_depth")
            path_obj = result.get_path(label="shortest_path")

            # Extract relationship name from the last Relationship vertex in the path
            rel_name = ""
            if path_obj:
                path_nodes = list(path_obj.nodes)
                if len(path_nodes) >= 2:
                    rel_vertex = path_nodes[-2]
                    rel_name = rel_vertex.get("name", "")

            path_data = self._extract_path(path_obj) if path_obj else PathData(nodes=[], relationships=[], depth=0)

            results.append(
                DependencyNodeData(
                    uuid=target.get("uuid", ""),
                    kind=target.get("kind", ""),
                    display_label=target.get("display_label", target.get("kind", "")),
                    depth=int(depth) if depth else 0,
                    relationship_name=rel_name,
                    path=path_data,
                )
            )
        return results
