from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core.timestamp import Timestamp
from infrahub.graph_traversal.path import PathTraversalQuery
from infrahub.graph_traversal.reachable import (
    ReachablePathsQuery,
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
    """Run a path-traversal plan as a single ``SHORTEST k`` search.

    One quantified-path-pattern query returns up to ``max_paths`` paths to the
    anchored destination, shortest first. The search walks Neo4j's frontier and
    stops once the budget is filled, so shallow targets return without exploring
    the full ``max_depth`` cone. When ``timeout_seconds`` is set the query runs
    under that server-side transaction timeout so a pathological search aborts
    rather than overloading the database.
    """

    def __init__(
        self,
        *,
        db: InfrahubDatabase,
        branch: Branch,
        renderer: GraphTraversalCypherRenderer,
        timeout_seconds: float | None = None,
    ) -> None:
        self._db = db
        self._branch = branch
        self._renderer = renderer
        self._timeout_seconds = timeout_seconds

    async def run(self, *, plan: Plan, source_id: str, max_paths: int, at: Timestamp | None = None) -> list[PathData]:
        at = at if at is not None else Timestamp()
        query = await PathTraversalQuery.init(
            db=self._db,
            branch=self._branch,
            at=at,
            renderer=self._renderer,
            plan=plan,
            source_id=source_id,
            max_paths=max_paths,
        )
        await query.execute(db=self._db, timeout_seconds=self._timeout_seconds)
        return query.get_paths()


class ReachableNodesExecutor:
    """Discover terminals once, then enumerate paths depth-by-depth, shallowest first.

    Phase 1 finds up to ``max_targets`` distinct terminal nodes. Phase 2 then
    runs once per feasible depth with a shrinking ``max_paths`` budget, so the
    deepest (most expensive) branches are never evaluated once the budget is
    full. Results keep the shortest-first ordering of a single all-depths
    query: the loop ascends depth and each per-depth query orders its rows
    internally.
    """

    def __init__(
        self,
        *,
        db: InfrahubDatabase,
        branch: Branch,
        renderer: GraphTraversalCypherRenderer,
        timeout_seconds: float | None = None,
    ) -> None:
        self._db = db
        self._branch = branch
        self._renderer = renderer
        self._timeout_seconds = timeout_seconds

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
        await targets_query.execute(db=self._db, timeout_seconds=self._timeout_seconds)
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
            await paths_query.execute(db=self._db, timeout_seconds=self._timeout_seconds)
            collected.extend(paths_query.get_reachable_nodes())
        return collected

    async def _run_shortest(
        self, *, plan: Plan, source_id: str, terminal_uuids: list[str], max_paths: int, at: Timestamp
    ) -> list[ReachableNodeData]:
        """Shortest path(s) per target, resolved by ascending depth band.

        A target first reached at depth ``d`` is removed from the search before band
        ``d + 1`` runs, so each target contributes only its minimum-depth path(s). Every
        remaining target is resolved in one batched band query rather than one search apiece,
        so cost scales with the number of feasible bands, not with the number of targets.
        """
        collected: list[ReachableNodeData] = []
        remaining_targets = list(terminal_uuids)
        for depth in self._renderer.feasible_depths(plan=plan):
            if not remaining_targets:
                break
            budget = max_paths - len(collected)
            if budget <= 0:
                break
            paths_query = await ReachablePathsQuery.init(
                db=self._db,
                branch=self._branch,
                at=at,
                renderer=self._renderer,
                plan=plan,
                source_id=source_id,
                terminal_uuids=remaining_targets,
                max_paths=budget,
                depths={depth},
            )
            await paths_query.execute(db=self._db, timeout_seconds=self._timeout_seconds)
            rows = paths_query.get_reachable_nodes()
            collected.extend(rows)
            reached = {row.node.uuid for row in rows}
            remaining_targets = [t for t in remaining_targets if t not in reached]
        return collected
