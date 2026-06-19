from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

from infrahub.core.query import Query, QueryType
from infrahub.graph_traversal._extract import extract_path_from_result

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase
    from infrahub.graph_traversal._cypher import GraphTraversalCypherRenderer
    from infrahub.graph_traversal.planning.models import Plan
    from infrahub.graph_traversal.results import PathData

# Backstop on the number of nodes returned by a single BFS frontier expansion. A realistic
# infrastructure graph stays far below this; it exists only so a pathological mega-frontier
# is truncated rather than exhausting memory. Setting a (large) limit also routes the query
# through the single-execution path instead of the internal size-limit pagination loop,
# which assumes an internal LIMIT the frontier query intentionally omits.
FRONTIER_HARD_LIMIT = 1_000_000


class FrontierHopQuery(Query):
    """One BFS step of the bidirectional by-id search: expand the frontier by one hop.

    Returns the distinct legal neighbour uuids of the nodes in ``frontier``. The caller
    loops this depth-by-depth, recording each node's first-seen depth.
    """

    name = "path_traversal_frontier_hop"
    type = QueryType.READ
    insert_return = False
    insert_limit = True

    def __init__(
        self,
        *,
        renderer: GraphTraversalCypherRenderer,
        plan: Plan,
        source_id: str,
        target_id: str,
        frontier_uuids: list[str],
        direction: Literal["forward", "backward"],
        seed: bool,
        **kwargs: Any,
    ) -> None:
        self._renderer = renderer
        self._plan = plan
        self._source_id = source_id
        self._target_id = target_id
        self._frontier_uuids = frontier_uuids
        self._direction = direction
        self._seed = seed
        kwargs.setdefault("limit", FRONTIER_HARD_LIMIT)
        super().__init__(**kwargs)

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        rendered = self._renderer.render_frontier_hop(
            plan=self._plan,
            source_id=self._source_id,
            target_id=self._target_id,
            frontier_uuids=self._frontier_uuids,
            direction=self._direction,
            seed=self._seed,
            at=self.at,
        )
        self.add_to_query(rendered.text)
        self.params.update(rendered.params)
        self.return_labels = list(rendered.return_labels)

    def get_neighbor_uuids(self) -> list[str]:
        return [uuid for result in self.get_results() if (uuid := result.get_as_str(label="uuid"))]


class PathJoinQuery(Query):
    """Reconstruct the shortest paths of one depth tier of the bidirectional by-id search."""

    name = "path_traversal_join"
    type = QueryType.READ
    insert_return = False
    insert_limit = False

    def __init__(
        self,
        *,
        renderer: GraphTraversalCypherRenderer,
        plan: Plan,
        source_id: str,
        target_id: str,
        left_len: int,
        right_len: int,
        tier_middles: list[str],
        tier_limit: int,
        **kwargs: Any,
    ) -> None:
        self._renderer = renderer
        self._plan = plan
        self._source_id = source_id
        self._target_id = target_id
        self._left_len = left_len
        self._right_len = right_len
        self._tier_middles = tier_middles
        self._tier_limit = tier_limit
        super().__init__(**kwargs)

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        rendered = self._renderer.render_canonical_join(
            plan=self._plan,
            source_id=self._source_id,
            target_id=self._target_id,
            left_len=self._left_len,
            right_len=self._right_len,
            tier_middles=self._tier_middles,
            tier_limit=self._tier_limit,
            at=self.at,
        )
        self.add_to_query(rendered.text)
        self.params.update(rendered.params)
        self.return_labels = list(rendered.return_labels)

    def get_paths(self) -> list[PathData]:
        paths: list[PathData] = []
        for result in self.get_results():
            path = extract_path_from_result(result)
            if path is not None:
                paths.append(path)
        return paths
