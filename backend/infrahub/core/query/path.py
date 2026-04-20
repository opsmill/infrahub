from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from infrahub.core import registry
from infrahub.core.constants import RelationshipDirection
from infrahub.core.query import Query, QueryType

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase


@dataclass(frozen=True)
class PathNodeData:
    uuid: str
    kind: str
    display_label: str


@dataclass(frozen=True)
class PathRelationshipData:
    uuid: str
    name: str
    direction: RelationshipDirection


@dataclass(frozen=True)
class PathData:
    nodes: list[PathNodeData]
    relationships: list[PathRelationshipData]
    depth: int


DEFAULT_EXCLUDED_NAMESPACES = (
    "Core",
    "Internal",
    "Builtin",
    "Lineage",
    "Profile",
    "Template",
)


def extract_path_data(path_obj: Any) -> PathData:
    """Convert a Neo4j Path object into PathData.

    Paths alternate Node vertex, Relationship vertex, Node vertex, ... where
    each hop between user-visible nodes is two edges.
    """
    raw_nodes = list(path_obj.nodes)
    raw_rels = list(path_obj.relationships)

    path_nodes: list[PathNodeData] = []
    path_relationships: list[PathRelationshipData] = []

    for i, vertex in enumerate(raw_nodes):
        if i % 2 == 0:
            path_nodes.append(
                PathNodeData(
                    uuid=vertex.get("uuid", ""),
                    kind=vertex.get("kind", ""),
                    display_label=vertex.get("display_label", vertex.get("kind", "")),
                )
            )
            continue

        direction = RelationshipDirection.OUTBOUND
        if i > 0 and (i - 1) < len(raw_rels):
            incoming_edge = raw_rels[i - 1]
            prior_node = raw_nodes[i - 1]
            if (
                incoming_edge is not None
                and hasattr(incoming_edge, "start_node")
                and incoming_edge.start_node != prior_node.element_id
            ):
                direction = RelationshipDirection.INBOUND

        path_relationships.append(
            PathRelationshipData(
                uuid=vertex.get("uuid", ""),
                name=vertex.get("name", ""),
                direction=direction,
            )
        )

    depth = len(path_nodes) - 1 if len(path_nodes) > 1 else 0
    return PathData(nodes=path_nodes, relationships=path_relationships, depth=depth)


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
        kind_filter: list[str] | None = None,
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
        self.kind_filter = kind_filter or []
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
        self.params["default_branch"] = registry.default_branch

        max_edge_length = self.max_depth * 2

        where_clauses = [f"all(r IN relationships(path) WHERE ({branch_filter}))"]

        if self.excluded_namespaces:
            self.params["excluded_namespaces"] = self.excluded_namespaces
            where_clauses.append(
                "all(n IN nodes(path) WHERE "
                "n.uuid IN [$source_uuid, $target_uuid] "
                "OR NOT n:Node "
                "OR NOT n.namespace IN $excluded_namespaces)"
            )

        if self.excluded_kinds:
            self.params["excluded_kinds"] = self.excluded_kinds
            where_clauses.append(
                "all(n IN nodes(path) WHERE "
                "n.uuid IN [$source_uuid, $target_uuid] "
                "OR NOT n:Node "
                "OR NOT n.kind IN $excluded_kinds)"
            )

        if self.kind_filter:
            # Match against all labels on the node so generic kinds (which are labels
            # on concrete nodes but not stored as `kind`) are supported.
            self.params["kind_filter"] = self.kind_filter
            where_clauses.append(
                "all(n IN nodes(path) WHERE "
                "n.uuid IN [$source_uuid, $target_uuid] "
                "OR NOT n:Node "
                "OR any(l IN labels(n) WHERE l IN $kind_filter))"
            )

        if self.relationship_filter:
            self.params["relationship_filter"] = self.relationship_filter
            where_clauses.append("all(n IN nodes(path) WHERE NOT n:Relationship OR n.name IN $relationship_filter)")

        where_str = " AND ".join(where_clauses)
        query_params: dict[str, Any] = {
            "max_edge_length": max_edge_length,
            "where_str": where_str,
            "max_paths": self.max_paths,
            "branch_filter": branch_filter,
        }

        if self.branch.is_default:
            # On the default branch we can require every edge to be active AND
            # verify no twin deleted edge exists between the same pair of vertices
            # (status="deleted" edges can coexist with status="active" ones when
            # a relationship has been recreated).
            query_params["candidate_limit"] = self.max_paths
            query = (
                """
            MATCH (source:Node { uuid: $source_uuid }), (target:Node { uuid: $target_uuid })
            MATCH path = (source)-[:IS_RELATED*2..%(max_edge_length)s]-(target)
            WHERE %(where_str)s
            AND all(r IN relationships(path) WHERE r.status = "active")
            AND none(
                r IN relationships(path) WHERE exists(
                    (startNode(r))-[:IS_RELATED {branch: $default_branch, status: "deleted"}]-(endNode(r))
                )
            )
            RETURN path, length(path) AS path_length
            ORDER BY path_length ASC
            LIMIT %(max_paths)s
            """
                % query_params
            )
        else:
            # Off the default branch a candidate edge may be active on the default
            # branch but deleted on this branch. We take the latest-version edge
            # per (sn, en) pair (pattern mirrored from attribute.py) and require
            # each hop's latest version to be active.
            query_params["candidate_limit"] = self.max_paths * 5
            query = (
                """
            MATCH (source:Node { uuid: $source_uuid }), (target:Node { uuid: $target_uuid })
            MATCH path = (source)-[:IS_RELATED*2..%(max_edge_length)s]-(target)
            WHERE %(where_str)s
            WITH path, length(path) AS path_length
            ORDER BY path_length ASC
            LIMIT %(candidate_limit)s
            WITH path, path_length, relationships(path) AS rels
            UNWIND range(0, size(rels) - 1) AS idx
            WITH path, path_length, startNode(rels[idx]) AS sn, endNode(rels[idx]) AS en
            CALL (sn, en) {
                MATCH (sn)-[r:IS_RELATED]-(en)
                WHERE (%(branch_filter)s)
                RETURN r
                ORDER BY r.branch_level DESC, r.from DESC, r.status ASC
                LIMIT 1
            }
            WITH path, path_length, r.status = "active" AS edge_active
            WITH path, path_length, collect(edge_active) AS edge_statuses
            WHERE ALL(s IN edge_statuses WHERE s = true)
            RETURN DISTINCT path, path_length
            ORDER BY path_length ASC
            LIMIT %(max_paths)s
            """
                % query_params
            )

        self.add_to_query(query)
        self.return_labels = ["path", "length(path) AS path_length"]

    def get_paths(self) -> list[PathData]:
        paths: list[PathData] = []
        for result in self.get_results():
            path_obj = result.get_path(label="path")
            if path_obj is None:
                continue
            paths.append(extract_path_data(path_obj))
        return paths
