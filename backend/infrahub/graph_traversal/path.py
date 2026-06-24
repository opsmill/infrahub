from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

from infrahub.core.query import Query, QueryType
from infrahub.graph_traversal._extract import extract_path_from_result

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase
    from infrahub.graph_traversal._cypher import GraphTraversalCypherRenderer
    from infrahub.graph_traversal.planning.models import Plan
    from infrahub.graph_traversal.results import PathData


class BfsQuery(Query):
    """The full bidirectional-search BFS from one anchor, run as a single query.

    Returns one ``frontiers`` row: a list whose ``i``-th element lists the node uuids first
    reached at depth ``i + 1`` from the anchor.
    """

    name = "path_traversal_bfs"
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
        direction: Literal["forward", "backward"],
        max_hops: int,
        **kwargs: Any,
    ) -> None:
        self._renderer = renderer
        self._plan = plan
        self._source_id = source_id
        self._target_id = target_id
        self._direction = direction
        self._max_hops = max_hops
        super().__init__(**kwargs)

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        rendered = self._renderer.render_bfs(
            plan=self._plan,
            source_id=self._source_id,
            target_id=self._target_id,
            direction=self._direction,
            max_hops=self._max_hops,
            at=self.at,
        )
        self.add_to_query(rendered.text)
        self.params.update(rendered.params)
        self.return_labels = list(rendered.return_labels)

    def get_frontiers(self) -> list[list[str]]:
        """Per-depth uuid lists; ``frontiers[i]`` are the nodes first reached at depth ``i + 1``."""
        result = self.get_result()
        if result is None:
            return []
        return result.get_as_list_of_type(label="frontiers", return_type=list)


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
