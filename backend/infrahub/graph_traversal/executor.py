from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core.timestamp import Timestamp
from infrahub.graph_traversal.path import PathTraversalQuery
from infrahub.graph_traversal.reachable import (
    ReachablePathsQuery,
    ReachableShortestPathsQuery,
    ReachableTargetsQuery,
)

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase
    from infrahub.graph_traversal._cypher import GraphTraversalCypherRenderer
    from infrahub.graph_traversal.planning.models import Plan
    from infrahub.graph_traversal.reachable import ReachableNodeData
    from infrahub.graph_traversal.results import PathData


class PathTraversalExecutor:
    """Run a path-traversal plan depth-by-depth, shallowest first.

    Each feasible depth executes as its own query with the remaining path
    budget, so deeper branches are never evaluated once ``max_paths`` paths
    have been collected. Results keep the shortest-first ordering of a single
    all-depths query: the loop ascends depth and each per-depth query orders
    its rows internally.
    """

    def __init__(self, *, db: InfrahubDatabase, branch: Branch, renderer: GraphTraversalCypherRenderer) -> None:
        self._db = db
        self._branch = branch
        self._renderer = renderer

    async def run(self, *, plan: Plan, source_id: str, max_paths: int, at: Timestamp | None = None) -> list[PathData]:
        at = at if at is not None else Timestamp()
        collected: list[PathData] = []
        for depth in self._renderer.feasible_depths(plan=plan):
            remaining = max_paths - len(collected)
            if remaining <= 0:
                break
            query = await PathTraversalQuery.init(
                db=self._db,
                branch=self._branch,
                at=at,
                renderer=self._renderer,
                plan=plan,
                source_id=source_id,
                max_paths=remaining,
                depths={depth},
            )
            await query.execute(db=self._db)
            collected.extend(query.get_paths())
        return collected


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
