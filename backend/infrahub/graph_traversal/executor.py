from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from infrahub.core.timestamp import Timestamp
from infrahub.graph_traversal.path import FrontierHopQuery, PathJoinQuery
from infrahub.graph_traversal.planning.models import TerminalById
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
    """Find paths between two specific nodes with a bidirectional ("meet-in-the-middle") search.

    A node-bounded BFS frontier is expanded inward from each anchor to depth
    ``ceil(max_depth / 2)``, building a per-node shortest-distance map from each end. Nodes
    reached from both ends are candidate middles; the shortest connecting distance is the
    minimum of ``forward + backward`` over them. Paths are then reconstructed tier by tier in
    ascending depth: for tier ``d`` the canonical split is ``floor(d/2)`` / ``ceil(d/2)`` and
    the join runs only over the middles at exactly those distances. This avoids the
    exponential path enumeration of a single deep ``SHORTEST k`` search to a specific target.

    Results are deterministic and monotonic in ``max_paths``: tiers are emitted in ascending
    depth and ordered within a tier by a total-order key, so the output is a stable prefix of a
    fixed global order and raising ``max_paths`` only appends paths. When ``timeout_seconds`` is
    set each query runs under that server-side transaction timeout.
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
        if not isinstance(plan.terminal_predicate, TerminalById):
            raise ValueError("PathTraversalExecutor handles TerminalById plans only")
        at = at if at is not None else Timestamp()
        target_id = plan.terminal_predicate.node_id
        max_depth = plan.max_depth
        half_depth = (max_depth + 1) // 2

        forward_depth_map = await self._bfs(
            plan=plan,
            source_id=source_id,
            target_id=target_id,
            seed_uuid=source_id,
            direction="forward",
            max_hops=half_depth,
            at=at,
        )
        backward_depth_map = await self._bfs(
            plan=plan,
            source_id=source_id,
            target_id=target_id,
            seed_uuid=target_id,
            direction="backward",
            max_hops=half_depth,
            at=at,
        )

        common_uuids = forward_depth_map.keys() & backward_depth_map.keys()
        if not common_uuids:
            return []
        min_join = min(forward_depth_map[node] + backward_depth_map[node] for node in common_uuids)

        collected: list[PathData] = []
        for depth in range(min_join, max_depth + 1):
            if len(collected) >= max_paths:
                break
            left_len = depth // 2
            right_len = depth - left_len
            middles = [
                node
                for node in common_uuids
                if forward_depth_map[node] == left_len and backward_depth_map[node] == right_len
            ]
            if not middles:
                continue
            query = await PathJoinQuery.init(
                db=self._db,
                branch=self._branch,
                at=at,
                renderer=self._renderer,
                plan=plan,
                source_id=source_id,
                target_id=target_id,
                left_len=left_len,
                right_len=right_len,
                tier_middles=middles,
                tier_limit=max_paths - len(collected),
            )
            await query.execute(db=self._db, timeout_seconds=self._timeout_seconds)
            collected.extend(query.get_paths())
        return collected[:max_paths]

    async def _bfs(
        self,
        *,
        plan: Plan,
        source_id: str,
        target_id: str,
        seed_uuid: str,
        direction: Literal["forward", "backward"],
        max_hops: int,
        at: Timestamp,
    ) -> dict[str, int]:
        """BFS from ``seed_uuid`` to ``max_hops``, returning each node's first-seen (shortest) depth.

        The first hop resolves the anchor to its active same-UUID vertex; later hops expand
        the accumulated frontier by uuid.
        """
        distance_map: dict[str, int] = {seed_uuid: 0}
        frontier = [seed_uuid]
        for hop in range(1, max_hops + 1):
            if not frontier:
                break
            query = await FrontierHopQuery.init(
                db=self._db,
                branch=self._branch,
                at=at,
                renderer=self._renderer,
                plan=plan,
                source_id=source_id,
                target_id=target_id,
                frontier_uuids=frontier,
                direction=direction,
                seed=hop == 1,
            )
            await query.execute(db=self._db, timeout_seconds=self._timeout_seconds)
            next_frontier = [uuid for uuid in query.get_neighbor_uuids() if uuid not in distance_map]
            for uuid in next_frontier:
                distance_map[uuid] = hop
            frontier = next_frontier
        return distance_map


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
