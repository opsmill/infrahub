from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from infrahub.core.query import Query, QueryType

if TYPE_CHECKING:
    from neo4j.graph import Path as Neo4jPath

    from infrahub.database import InfrahubDatabase


@dataclass(frozen=True)
class PathNodeData:
    uuid: str
    kind: str
    label: str
    display_label: str
    hfid: list[str]


@dataclass(frozen=True)
class PathHopData:
    node: PathNodeData
    # Schema relationship identifier (e.g. "device_interfaces") of the edge
    # traversed to reach this node from the previous hop. None on the first hop.
    relationship_identifier: str | None


@dataclass(frozen=True)
class PathData:
    hops: list[PathHopData]
    depth: int


DEFAULT_EXCLUDED_NAMESPACES = (
    "Core",
    "Internal",
    "Builtin",
    "Lineage",
    "Profile",
    "Template",
)


def extract_path_data(path_obj: Neo4jPath) -> PathData:
    """Convert a Neo4j Path object into PathData.

    Paths alternate Node vertex, Relationship vertex, Node vertex, ... where
    each hop between user-visible nodes is two edges. Emits a list of hops where
    the first hop has `relationship=None` and each subsequent hop carries the
    Relationship vertex that connects it to the previous node.
    """
    raw_nodes = list(path_obj.nodes)

    hops: list[PathHopData] = []
    pending_identifier: str | None = None

    for i, vertex in enumerate(raw_nodes):
        if i % 2 == 0:
            node = PathNodeData(
                uuid=vertex.get("uuid", ""),
                kind=vertex.get("kind", ""),
                label="",
                display_label=vertex.get("display_label", vertex.get("kind", "")),
                hfid=[],
            )
            hops.append(PathHopData(node=node, relationship_identifier=pending_identifier))
            pending_identifier = None
            continue

        pending_identifier = vertex.get("name", "")

    depth = len(hops) - 1 if len(hops) > 1 else 0
    return PathData(hops=hops, depth=depth)


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

        # For each pair of adjacent vertices on a candidate path we take the
        # latest-version IS_RELATED edge (highest branch_level, then most
        # recent `from`, then active before deleted on ties) and require that
        # latest version to be active. This handles deleted-then-recreated
        # relationships and per-branch overrides uniformly. Off-default
        # branches need a wider candidate pool because superseded edges from
        # the origin branch produce more "false" candidates that get filtered.
        query_params["candidate_limit"] = self.max_paths if self.branch.is_default else self.max_paths * 5
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
