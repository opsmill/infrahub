from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

from infrahub.core.query import Query, QueryType
from infrahub.graph_traversal._extract import extract_half_path_from_result, extract_path_from_result

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase
    from infrahub.graph_traversal._cypher import GraphTraversalCypherRenderer
    from infrahub.graph_traversal.planning.models import Plan
    from infrahub.graph_traversal.results import PathData, PathHopData


class BfsHopQuery(Query):
    """One hop of the bidirectional-search BFS from one anchor.

    ``seed=True`` resolves the active anchor (``anchor_id``) and expands it; ``seed=False``
    expands every node in ``frontier`` by one legal edge. ``get_frontier()`` returns the
    neighbour uuids reached by the hop.
    """

    name = "path_traversal_bfs_hop"
    type = QueryType.READ
    insert_return = False
    insert_limit = False

    def __init__(
        self,
        *,
        renderer: GraphTraversalCypherRenderer,
        plan: Plan,
        direction: Literal["forward", "backward"],
        seed: bool,
        anchor_id: str,
        frontier: list[str],
        **kwargs: Any,
    ) -> None:
        self._renderer = renderer
        self._plan = plan
        self._direction = direction
        self._seed = seed
        self._anchor_id = anchor_id
        self._frontier = frontier
        super().__init__(**kwargs)

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        rendered = self._renderer.render_bfs_hop(
            plan=self._plan, direction=self._direction, seed=self._seed, at=self.at
        )
        self.add_to_query(rendered.text)
        self.params.update(rendered.params)
        if self._seed:
            self.params["anchor_id"] = self._anchor_id
        else:
            self.params["frontier"] = self._frontier
        self.return_labels = list(rendered.return_labels)

    def get_frontier(self) -> list[str]:
        """The neighbour uuids reached by this hop."""
        result = self.get_result()
        if result is None:
            return []
        return result.get_as_list_of_type(label="frontier", return_type=str)


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


class _HalfPathsQuery(Query):
    """Base for the exhaustive by-id half-enumeration queries.

    Subclasses render one half (all simple paths of a fixed length from one fixed anchor); this
    base exposes the shared projection as ``(mid_uuid, hops)`` rows.
    """

    type = QueryType.READ
    insert_return = False
    insert_limit = False

    def get_half_paths(self) -> list[tuple[str, list[PathHopData]]]:
        """Each row as ``(mid_uuid, hops)``; ``hops`` runs outward from the fixed anchor."""
        halves: list[tuple[str, list[PathHopData]]] = []
        for result in self.get_results():
            half = extract_half_path_from_result(result)
            if half is not None:
                halves.append(half)
        return halves


class LeftHalfPathsQuery(_HalfPathsQuery):
    """All length-``length`` simple paths from the source; each row's ``mid_uuid`` is the endpoint."""

    name = "path_traversal_half_left"

    def __init__(
        self,
        *,
        renderer: GraphTraversalCypherRenderer,
        plan: Plan,
        source_id: str,
        length: int,
        limit: int,
        **kwargs: Any,
    ) -> None:
        self._renderer = renderer
        self._plan = plan
        self._source_id = source_id
        self._length = length
        self._limit = limit
        super().__init__(**kwargs)

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        rendered = self._renderer.render_half_from_source(
            plan=self._plan, source_id=self._source_id, length=self._length, limit=self._limit, at=self.at
        )
        self.add_to_query(rendered.text)
        self.params.update(rendered.params)
        self.return_labels = list(rendered.return_labels)


class RightHalfPathsQuery(_HalfPathsQuery):
    """All length-``length`` simple paths into the target from a node in ``middles``; ``mid_uuid`` is the start."""

    name = "path_traversal_half_right"

    def __init__(
        self,
        *,
        renderer: GraphTraversalCypherRenderer,
        plan: Plan,
        source_id: str,
        target_id: str,
        length: int,
        middles: list[str],
        limit: int,
        **kwargs: Any,
    ) -> None:
        self._renderer = renderer
        self._plan = plan
        self._source_id = source_id
        self._target_id = target_id
        self._length = length
        self._middles = middles
        self._limit = limit
        super().__init__(**kwargs)

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        rendered = self._renderer.render_half_to_target(
            plan=self._plan,
            source_id=self._source_id,
            target_id=self._target_id,
            length=self._length,
            middles=self._middles,
            limit=self._limit,
            at=self.at,
        )
        self.add_to_query(rendered.text)
        self.params.update(rendered.params)
        self.return_labels = list(rendered.return_labels)
