from __future__ import annotations

from collections import defaultdict
from operator import itemgetter
from typing import TYPE_CHECKING, Literal

from infrahub.core.timestamp import Timestamp
from infrahub.exceptions import QueryTimeoutError
from infrahub.graph_traversal.path import BfsHopQuery, LeftHalfPathsQuery, PathJoinQuery, RightHalfPathsQuery
from infrahub.graph_traversal.planning.models import TerminalById
from infrahub.graph_traversal.reachable import (
    ReachablePathsQuery,
    ReachableTargetsQuery,
)
from infrahub.graph_traversal.results import PathData, PathNodeData, PathTraversalResult

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase
    from infrahub.graph_traversal._cypher import GraphTraversalCypherRenderer
    from infrahub.graph_traversal.planning.models import Plan
    from infrahub.graph_traversal.reachable import ReachableNodeData
    from infrahub.graph_traversal.results import PathHopData
    from infrahub.graph_traversal.runner import QueryRunner


# Exhaustive mode joins half-paths in memory; if a single tier's half-path set would exceed this
# many rows the search truncates instead, keeping the in-memory join bounded.
DEFAULT_EXHAUSTIVE_HALF_CAP = 10_000


class PathTraversalExecutor:
    """Find paths between two specific nodes with a bidirectional ("meet-in-the-middle") search.

    A node-bounded BFS frontier is expanded inward from each anchor, building a per-node
    shortest-distance map from each end. Paths are reconstructed tier by tier in ascending
    depth: for tier ``d`` the canonical split is ``floor(d/2)`` / ``ceil(d/2)`` and the join
    runs only over the middles at exactly those distances. The frontiers are expanded lazily —
    each side only to the radius the current tier needs — so a shallow connection never pays for
    expansion to ``ceil(max_depth / 2)``. This avoids the exponential path enumeration of a
    single deep ``SHORTEST k`` search to a specific target.

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
        query_runner: QueryRunner,
        timeout_seconds: float | None = None,
        exhaustive_half_cap: int = DEFAULT_EXHAUSTIVE_HALF_CAP,
    ) -> None:
        self._db = db
        self._branch = branch
        self._renderer = renderer
        self._query_runner = query_runner
        self._timeout_seconds = timeout_seconds
        # Exhaustive mode retrieves half-paths into memory to join them; a tier whose half-path set
        # exceeds this cap is abandoned (the search truncates) rather than risking an unbounded join.
        self._exhaustive_half_cap = exhaustive_half_cap

    async def run(
        self,
        *,
        plan: Plan,
        source_id: str,
        max_paths: int,
        shortest_paths_only: bool = True,
        at: Timestamp | None = None,
    ) -> PathTraversalResult:
        if not isinstance(plan.terminal_predicate, TerminalById):
            raise ValueError("PathTraversalExecutor handles TerminalById plans only")
        at = at if at is not None else Timestamp()
        target_id = plan.terminal_predicate.node_id
        if shortest_paths_only:
            return await self._run_shortest(
                plan=plan, source_id=source_id, target_id=target_id, max_paths=max_paths, at=at
            )
        return await self._run_exhaustive(
            plan=plan, source_id=source_id, target_id=target_id, max_paths=max_paths, at=at
        )

    async def _run_shortest(
        self, *, plan: Plan, source_id: str, target_id: str, max_paths: int, at: Timestamp
    ) -> PathTraversalResult:
        """Shortest path(s) through each intermediate, via a pinned-middle canonical join per tier.

        The BFS frontiers are expanded **lazily**: for each tier ``d`` ascending, each side is
        grown only to the radius that tier needs (``floor(d/2)`` forward, ``ceil(d/2)`` backward).
        The search stops as soon as ``max_paths`` is reached or both frontiers are exhausted, so a
        shallow connection never pays for expansion all the way to ``ceil(max_depth/2)``.
        """
        fwd_dist: dict[str, int] = {source_id: 0}
        bwd_dist: dict[str, int] = {target_id: 0}
        fwd_frontier = [source_id]
        bwd_frontier = [target_id]
        fwd_radius = 0
        bwd_radius = 0

        collected: list[PathData] = []
        for depth in range(1, plan.max_depth + 1):
            if len(collected) >= max_paths:
                break
            left_len = depth // 2
            right_len = depth - left_len
            try:
                while bwd_radius < right_len and bwd_frontier:
                    neighbours = await self._run_bfs_hop(
                        plan=plan,
                        direction="backward",
                        seed=bwd_radius == 0,
                        anchor_id=target_id,
                        frontier=bwd_frontier,
                        at=at,
                    )
                    bwd_radius += 1
                    bwd_frontier = [uuid for uuid in neighbours if uuid not in bwd_dist]
                    for uuid in bwd_frontier:
                        bwd_dist[uuid] = bwd_radius
                while fwd_radius < left_len and fwd_frontier:
                    neighbours = await self._run_bfs_hop(
                        plan=plan,
                        direction="forward",
                        seed=fwd_radius == 0,
                        anchor_id=source_id,
                        frontier=fwd_frontier,
                        at=at,
                    )
                    fwd_radius += 1
                    fwd_frontier = [uuid for uuid in neighbours if uuid not in fwd_dist]
                    for uuid in fwd_frontier:
                        fwd_dist[uuid] = fwd_radius
            except QueryTimeoutError:
                return PathTraversalResult(paths=collected[:max_paths], truncated_at_depth=depth)

            if fwd_radius < left_len or bwd_radius < right_len:
                break  # a frontier is exhausted before this depth, so no deeper path can exist

            middles = [
                node
                for node in fwd_dist.keys() & bwd_dist.keys()
                if fwd_dist[node] == left_len and bwd_dist[node] == right_len
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
            try:
                await self._query_runner.run(query, db=self._db, timeout_seconds=self._timeout_seconds)
            except QueryTimeoutError:
                return PathTraversalResult(paths=collected[:max_paths], truncated_at_depth=depth)
            collected.extend(query.get_paths())
        return PathTraversalResult(paths=collected[:max_paths])

    async def _run_bfs_hop(
        self,
        *,
        plan: Plan,
        direction: Literal["forward", "backward"],
        seed: bool,
        anchor_id: str,
        frontier: list[str],
        at: Timestamp,
    ) -> list[str]:
        """Run one BFS expansion and return the neighbour uuids it reaches (not yet deduped).

        ``seed`` (the radius-0 hop) resolves and expands the active anchor; otherwise ``frontier``
        is expanded. The caller dedupes the result against the nodes it has already seen.
        """
        query = await BfsHopQuery.init(
            db=self._db,
            branch=self._branch,
            at=at,
            renderer=self._renderer,
            plan=plan,
            direction=direction,
            seed=seed,
            anchor_id=anchor_id,
            frontier=frontier,
        )
        await self._query_runner.run(query, db=self._db, timeout_seconds=self._timeout_seconds)
        return query.get_frontier()

    async def _run_exhaustive(
        self, *, plan: Plan, source_id: str, target_id: str, max_paths: int, at: Timestamp
    ) -> PathTraversalResult:
        """All loopless paths up to ``max_paths``, shortest-first, via per-tier half-enumeration.

        For each tier ``d`` ascending, enumerate every length-``floor(d/2)`` simple path from the
        source and every length-``ceil(d/2)`` simple path into the target (starting from the left
        halves' endpoints), then join each disjoint (left, right) pair on its shared middle. This
        recovers paths whose midpoint is not at its shortest distance — the routes the pinned join
        misses — without the exponential single-direction enumeration of a deep target search.
        """
        start_node = PathNodeData(uuid=source_id, kind=plan.source_kind)
        cap = self._exhaustive_half_cap
        # Retrieve one extra row so an over-cap set is detectable: more than ``cap`` rows means the
        # half-path set is too large to join in budget, so the search truncates at this depth.
        half_limit = cap + 1
        collected: list[PathData] = []
        for depth in range(1, plan.max_depth + 1):
            if len(collected) >= max_paths:
                break
            left_len = depth // 2
            right_len = depth - left_len

            if left_len == 0:
                left_halves: list[tuple[str, list[PathHopData]]] = [(source_id, [])]
            else:
                left_query = await LeftHalfPathsQuery.init(
                    db=self._db,
                    branch=self._branch,
                    at=at,
                    renderer=self._renderer,
                    plan=plan,
                    source_id=source_id,
                    length=left_len,
                    limit=half_limit,
                )
                try:
                    await self._query_runner.run(left_query, db=self._db, timeout_seconds=self._timeout_seconds)
                except QueryTimeoutError:
                    return PathTraversalResult(paths=collected[:max_paths], truncated_at_depth=depth)
                left_halves = left_query.get_half_paths()
                if len(left_halves) > cap:
                    return PathTraversalResult(paths=collected[:max_paths], truncated_at_depth=depth)
            if not left_halves:
                continue

            middles = sorted({mid for mid, _ in left_halves})
            right_query = await RightHalfPathsQuery.init(
                db=self._db,
                branch=self._branch,
                at=at,
                renderer=self._renderer,
                plan=plan,
                source_id=source_id,
                target_id=target_id,
                length=right_len,
                middles=middles,
                limit=half_limit,
            )
            try:
                await self._query_runner.run(right_query, db=self._db, timeout_seconds=self._timeout_seconds)
            except QueryTimeoutError:
                return PathTraversalResult(paths=collected[:max_paths], truncated_at_depth=depth)
            right_halves = right_query.get_half_paths()
            if len(right_halves) > cap:
                return PathTraversalResult(paths=collected[:max_paths], truncated_at_depth=depth)
            right_by_mid: dict[str, list[list[PathHopData]]] = defaultdict(list)
            for mid, hops in right_halves:
                right_by_mid[mid].append(hops)

            tier: list[tuple[str, PathData]] = []
            for mid, left_hops in left_halves:
                for right_hops in right_by_mid.get(mid, ()):
                    hops = left_hops + right_hops
                    node_uuids = [source_id, *(hop.node.uuid for hop in hops)]
                    if len(node_uuids) != len(set(node_uuids)):
                        continue  # drop non-simple joins (halves share a node besides the middle)
                    key = "".join(f"{hop.relationship_identifier}>{hop.node.uuid}" for hop in hops)
                    tier.append((key, PathData(start_node=start_node, hops=hops, depth=depth)))
            tier.sort(key=itemgetter(0))
            for _, path in tier:
                collected.append(path)
                if len(collected) >= max_paths:
                    break
        return PathTraversalResult(paths=collected[:max_paths])


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
