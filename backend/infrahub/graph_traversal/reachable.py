from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from infrahub.core.query import Query, QueryType
from infrahub.graph_traversal.planning.constants import DEFAULT_EXCLUDED_NAMESPACES
from infrahub.graph_traversal.results import PathData, PathHopData, PathNodeData

if TYPE_CHECKING:
    from neo4j.graph import Path as Neo4jPath

    from infrahub.database import InfrahubDatabase


@dataclass(frozen=True)
class ReachableNodeData:
    node: PathNodeData
    depth: int
    path: PathData


class ReachableNodesQuery(Query):
    name = "reachable_nodes_discovery"
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

        namespace_filter = ""
        if self.excluded_namespaces:
            self.params["excluded_namespaces"] = self.excluded_namespaces
            namespace_filter = (
                "AND all(n IN nodes(path) WHERE "
                "n.uuid = $source_uuid "
                "OR NOT n:Node "
                "OR any(l IN labels(n) WHERE l IN $target_kinds) "
                "OR NOT n.namespace IN $excluded_namespaces) "
            )

        query_params = {
            "max_edge_length": max_edge_length,
            "branch_filter": branch_filter,
            "namespace_filter": namespace_filter,
            "max_results": self.max_results,
        }

        # Match all labels on the target so generic kinds are supported.
        # Keep every distinct (target, path) pair up to max_results rather than
        # collapsing to one path per target — alternate routes through different
        # relationships are meaningful for impact analysis.
        query = (
            """
        MATCH (source:Node { uuid: $source_uuid })
        MATCH path = (source)-[:IS_RELATED*2..%(max_edge_length)s]-(target:Node)
        WHERE any(l IN labels(target) WHERE l IN $target_kinds)
        AND target.uuid <> $source_uuid
        AND all(r IN relationships(path) WHERE (%(branch_filter)s))
        %(namespace_filter)s
        WITH DISTINCT target, path, length(path) / 2 AS depth
        ORDER BY depth ASC, target.uuid ASC
        RETURN target.uuid AS target_uuid,
               target.kind AS target_kind,
               path,
               depth
        LIMIT %(max_results)s
        """
            % query_params
        )

        self.add_to_query(query)
        self.return_labels = [
            "target_uuid",
            "target_kind",
            "path",
            "depth",
        ]

    def get_reachable_nodes(self) -> list[ReachableNodeData]:
        results: list[ReachableNodeData] = []
        for result in self.get_results():
            path_obj = result.get_path(label="path")
            node = PathNodeData(
                uuid=result.get_as_str(label="target_uuid") or "",
                kind=result.get_as_str(label="target_kind") or "",
            )
            path_data = (
                self._extract_path_data(path_obj)
                if path_obj
                else PathData(start_node=PathNodeData(uuid=self.source_id, kind=""), hops=[], depth=0)
            )

            results.append(
                ReachableNodeData(
                    node=node,
                    depth=result.get_as_optional_type(label="depth", return_type=int) or 0,
                    path=path_data,
                )
            )
        return results

    @staticmethod
    def _extract_path_data(path_obj: Neo4jPath) -> PathData:
        """Convert a Neo4j Path object into PathData.

        Vertices alternate Node, Relationship, Node, Relationship, ...
        mirroring the ``IS_RELATED*N`` edge expansion. The first vertex is the
        ``start_node``; each subsequent Node vertex is a hop, paired with the
        preceding Relationship vertex's ``name`` as its identifier.
        """
        vertices = list(path_obj.nodes)
        if not vertices:
            return PathData(start_node=PathNodeData(uuid="", kind=""), hops=[], depth=0)

        start_node = PathNodeData(uuid=vertices[0].get("uuid", ""), kind=vertices[0].get("kind", ""))
        hops: list[PathHopData] = []
        pending_identifier = ""
        for i, vertex in enumerate(vertices[1:], start=1):
            if i % 2 == 1:
                pending_identifier = vertex.get("name", "")
            else:
                node = PathNodeData(uuid=vertex.get("uuid", ""), kind=vertex.get("kind", ""))
                hops.append(PathHopData(node=node, relationship_identifier=pending_identifier))
        return PathData(start_node=start_node, hops=hops, depth=len(hops))
