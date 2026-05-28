from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from infrahub.core.query import Query, QueryType
from infrahub.graph_traversal._extract import extract_path_from_result
from infrahub.graph_traversal.results import PathData, PathNodeData

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase
    from infrahub.graph_traversal._cypher import PathTraversalCypherRenderer
    from infrahub.graph_traversal.planning.models import Plan


@dataclass(frozen=True)
class ReachableNodeData:
    node: PathNodeData
    depth: int
    path: PathData


class ReachableNodesQuery(Query):
    """Execute a traversal plan and project reachable terminal nodes."""

    name = "reachable_nodes_discovery"
    type = QueryType.READ
    insert_return = False
    insert_limit = False

    def __init__(
        self,
        *,
        renderer: PathTraversalCypherRenderer,
        plan: Plan,
        source_id: str,
        max_targets: int,
        max_paths: int,
        **kwargs: Any,
    ) -> None:
        self._renderer = renderer
        self._plan = plan
        self._source_id = source_id
        self._max_targets = max_targets
        self._max_paths = max_paths
        super().__init__(**kwargs)

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        rendered = self._renderer.render(
            plan=self._plan,
            source_id=self._source_id,
            at=self.at,
            max_targets=self._max_targets,
            max_paths=self._max_paths,
        )
        self.add_to_query(rendered.text)
        self.params.update(rendered.params)
        self.return_labels = list(rendered.return_labels)

    def get_reachable_nodes(self) -> list[ReachableNodeData]:
        results: list[ReachableNodeData] = []
        for result in self.get_results():
            path = extract_path_from_result(result)
            if path is None or not path.hops:
                continue
            terminal = path.hops[-1].node
            results.append(
                ReachableNodeData(
                    node=PathNodeData(uuid=terminal.uuid, kind=terminal.kind),
                    depth=path.depth,
                    path=path,
                )
            )
        return results
