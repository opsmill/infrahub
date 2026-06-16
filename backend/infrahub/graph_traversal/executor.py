from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core.timestamp import Timestamp
from infrahub.graph_traversal.path import PathTraversalQuery

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase
    from infrahub.graph_traversal._cypher import GraphTraversalCypherRenderer
    from infrahub.graph_traversal.planning.models import Plan
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
