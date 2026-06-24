from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from infrahub.core.query import Query, QueryType
from infrahub.graph_traversal._extract import extract_path_from_result
from infrahub.graph_traversal.results import PathData, PathNodeData

if TYPE_CHECKING:
    from collections.abc import Iterable

    from infrahub.database import InfrahubDatabase
    from infrahub.graph_traversal._cypher import GraphTraversalCypherRenderer
    from infrahub.graph_traversal.planning.models import Plan


@dataclass(frozen=True)
class ReachableNodeData:
    node: PathNodeData
    depth: int
    path: PathData


def _reachable_from_results(results: Iterable[Any]) -> list[ReachableNodeData]:
    out: list[ReachableNodeData] = []
    for result in results:
        path = extract_path_from_result(result)
        if path is None or not path.hops:
            continue
        terminal = path.hops[-1].node
        out.append(
            ReachableNodeData(
                node=PathNodeData(uuid=terminal.uuid, kind=terminal.kind),
                depth=path.depth,
                path=path,
            )
        )
    return out


class ReachableTargetsQuery(Query):
    """Phase 1: discover up to ``max_targets`` distinct terminal-node uuids."""

    name = "reachable_nodes_targets"
    type = QueryType.READ
    insert_return = False
    insert_limit = False

    def __init__(
        self,
        *,
        renderer: GraphTraversalCypherRenderer,
        plan: Plan,
        source_id: str,
        max_targets: int,
        **kwargs: Any,
    ) -> None:
        self._renderer = renderer
        self._plan = plan
        self._source_id = source_id
        self._max_targets = max_targets
        super().__init__(**kwargs)

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        rendered = self._renderer.render_reachable_targets(
            plan=self._plan, source_id=self._source_id, at=self.at, max_targets=self._max_targets
        )
        self.add_to_query(rendered.text)
        self.params.update(rendered.params)
        self.return_labels = list(rendered.return_labels)

    def get_terminal_uuids(self) -> list[str]:
        result = self.get_result()
        if result is None:
            return []
        return result.get_as_list_of_type("terminal_uuids", return_type=str)


class ReachablePathsQuery(Query):
    """Phase 2: enumerate paths to a fixed terminal-uuid set, optionally one depth at a time."""

    name = "reachable_nodes_paths"
    type = QueryType.READ
    insert_return = False
    insert_limit = False

    def __init__(
        self,
        *,
        renderer: GraphTraversalCypherRenderer,
        plan: Plan,
        source_id: str,
        terminal_uuids: list[str],
        max_paths: int,
        depths: Iterable[int] | None = None,
        **kwargs: Any,
    ) -> None:
        self._renderer = renderer
        self._plan = plan
        self._source_id = source_id
        self._terminal_uuids = terminal_uuids
        self._max_paths = max_paths
        self._depths = depths
        super().__init__(**kwargs)

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        rendered = self._renderer.render_paths_to_targets(
            plan=self._plan,
            source_id=self._source_id,
            at=self.at,
            terminal_uuids=self._terminal_uuids,
            max_paths=self._max_paths,
            depths=self._depths,
        )
        self.add_to_query(rendered.text)
        self.params.update(rendered.params)
        self.return_labels = list(rendered.return_labels)

    def get_reachable_nodes(self) -> list[ReachableNodeData]:
        return _reachable_from_results(self.get_results())
