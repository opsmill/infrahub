from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from infrahub.core.query import Query, QueryType
from infrahub.core.timestamp import Timestamp
from infrahub.graph_traversal._extract import extract_path_from_result
from infrahub.graph_traversal.results import PathData, PathNodeData

if TYPE_CHECKING:
    from collections.abc import Iterable

    from infrahub.core.branch import Branch
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
        for result in self.get_results():
            uuids: list[str] = result.get_as_list_of_type("terminal_uuids", return_type=str)
            return uuids
        return []


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


class ReachableShortestPathsQuery(Query):
    """Phase 2 (shortest mode): all shortest path(s) to each terminal, one search per target."""

    name = "reachable_nodes_shortest_paths"
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
        **kwargs: Any,
    ) -> None:
        self._renderer = renderer
        self._plan = plan
        self._source_id = source_id
        self._terminal_uuids = terminal_uuids
        self._max_paths = max_paths
        super().__init__(**kwargs)

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        rendered = self._renderer.render_shortest_paths_to_targets(
            plan=self._plan,
            source_id=self._source_id,
            at=self.at,
            terminal_uuids=self._terminal_uuids,
            max_paths=self._max_paths,
        )
        self.add_to_query(rendered.text)
        self.params.update(rendered.params)
        self.return_labels = list(rendered.return_labels)

    def get_reachable_nodes(self) -> list[ReachableNodeData]:
        return _reachable_from_results(self.get_results())


class ReachableNodesExecutor:
    """Discover terminals once, then enumerate paths depth-by-depth, shallowest first.

    Phase 1 finds up to ``max_targets`` distinct terminal nodes. Phase 2 then
    runs once per feasible depth with a shrinking ``max_paths`` budget, so the
    deepest (most expensive) branches are never evaluated once the budget is
    full. Results keep the shortest-first ordering of a single all-depths
    query: the loop ascends depth and each per-depth query orders its rows
    internally.
    """

    def __init__(self, *, db: InfrahubDatabase, branch: Branch, renderer: GraphTraversalCypherRenderer) -> None:
        self._db = db
        self._branch = branch
        self._renderer = renderer

    async def run(
        self,
        *,
        plan: Plan,
        source_id: str,
        max_targets: int,
        max_paths: int,
        shortest_paths_only: bool = True,
        at: Timestamp | None = None,
    ) -> list[ReachableNodeData]:
        at = at if at is not None else Timestamp()

        targets_query = await ReachableTargetsQuery.init(
            db=self._db,
            branch=self._branch,
            at=at,
            renderer=self._renderer,
            plan=plan,
            source_id=source_id,
            max_targets=max_targets,
        )
        await targets_query.execute(db=self._db)
        terminal_uuids = targets_query.get_terminal_uuids()
        if not terminal_uuids:
            return []

        if shortest_paths_only:
            return await self._run_shortest(
                plan=plan, source_id=source_id, terminal_uuids=terminal_uuids, max_paths=max_paths, at=at
            )
        return await self._run_all_paths(
            plan=plan, source_id=source_id, terminal_uuids=terminal_uuids, max_paths=max_paths, at=at
        )

    async def _run_shortest(
        self, *, plan: Plan, source_id: str, terminal_uuids: list[str], max_paths: int, at: Timestamp
    ) -> list[ReachableNodeData]:
        query = await ReachableShortestPathsQuery.init(
            db=self._db,
            branch=self._branch,
            at=at,
            renderer=self._renderer,
            plan=plan,
            source_id=source_id,
            terminal_uuids=terminal_uuids,
            max_paths=max_paths,
        )
        await query.execute(db=self._db)
        return query.get_reachable_nodes()

    async def _run_all_paths(
        self, *, plan: Plan, source_id: str, terminal_uuids: list[str], max_paths: int, at: Timestamp
    ) -> list[ReachableNodeData]:
        collected: list[ReachableNodeData] = []
        for depth in self._renderer.feasible_depths(plan=plan):
            remaining = max_paths - len(collected)
            if remaining <= 0:
                break
            paths_query = await ReachablePathsQuery.init(
                db=self._db,
                branch=self._branch,
                at=at,
                renderer=self._renderer,
                plan=plan,
                source_id=source_id,
                terminal_uuids=terminal_uuids,
                max_paths=remaining,
                depths={depth},
            )
            await paths_query.execute(db=self._db)
            collected.extend(paths_query.get_reachable_nodes())
        return collected
