from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from infrahub.core.query import Query, QueryType
from infrahub.core.query.path import DEFAULT_EXCLUDED_NAMESPACES, PathData, extract_path_data

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase


@dataclass(frozen=True)
class ReachableNodeData:
    uuid: str
    kind: str
    display_label: str
    depth: int
    relationship_name: str
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
               coalesce(target.display_label, target.kind) AS target_display_label,
               path,
               depth,
               coalesce(nodes(path)[-2].name, "") AS relationship_name
        LIMIT %(max_results)s
        """
            % query_params
        )

        self.add_to_query(query)
        self.return_labels = [
            "target_uuid",
            "target_kind",
            "target_display_label",
            "path",
            "depth",
            "relationship_name",
        ]

    def get_reachable_nodes(self) -> list[ReachableNodeData]:
        results: list[ReachableNodeData] = []
        for result in self.get_results():
            path_obj = result.get_path(label="path")
            path_data = extract_path_data(path_obj) if path_obj else PathData(nodes=[], relationships=[], depth=0)

            results.append(
                ReachableNodeData(
                    uuid=result.get_as_str(label="target_uuid") or "",
                    kind=result.get_as_str(label="target_kind") or "",
                    display_label=result.get_as_str(label="target_display_label") or "",
                    depth=result.get_as_optional_type(label="depth", return_type=int) or 0,
                    relationship_name=result.get_as_str(label="relationship_name") or "",
                    path=path_data,
                )
            )
        return results
