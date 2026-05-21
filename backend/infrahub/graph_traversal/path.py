from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from infrahub.core.query import Query, QueryType
from infrahub.graph_traversal._cypher import render_plan_to_cypher
from infrahub.graph_traversal.results import PathData, PathHopData, PathNodeData

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase
    from infrahub.graph_traversal.planning.models import Plan


class PathTraversalQuery(Query):
    """Render a pre-built ``Plan`` into Cypher and execute it."""

    name = "path_traversal"
    type = QueryType.READ
    insert_return = False
    insert_limit = False

    def __init__(
        self,
        *,
        plan: Plan,
        source_id: str,
        max_paths: int = 10,
        **kwargs: Any,
    ) -> None:
        if plan.is_empty:
            raise ValueError("PathTraversalQuery requires a non-empty plan")

        self.plan = plan
        self.source_id = source_id
        self.max_paths = max_paths

        super().__init__(**kwargs)

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        rendered = render_plan_to_cypher(
            plan=self.plan,
            source_id=self.source_id,
            branch=self.branch,
            at=self.at,
            max_results=self.max_paths,
        )
        self.query_lines = [rendered.text]
        self.params.update(rendered.params)
        self.return_labels = list(rendered.return_labels)

    def get_paths(self) -> list[PathData]:
        paths: list[PathData] = []
        for result in self.get_results():
            # ``Query.get`` is typed for node/relationship returns; the QPP
            # projects a list[dict] (per the ``path_data`` projection in
            # ``_cypher.py``), so cast at the boundary.
            raw = cast("list[dict[str, Any]]", result.get(label="path_data"))
            if not raw:
                continue
            paths.append(self._extract_path_data(raw))
        return paths

    @staticmethod
    def _extract_path_data(path_data: list[dict[str, Any]]) -> PathData:
        """Build a ``PathData`` from the QPP's ``path_data`` projection.

        The projection alternates: even indices are ``:Node`` vertices
        (``uuid``/``kind`` populated), odd indices are ``:Relationship``
        vertices (``name`` populated). Mirrors the two-edge-per-hop shape of
        the QPP body in ``_cypher.py``.
        """
        hops: list[PathHopData] = []
        pending_identifier: str | None = None
        for i, vertex in enumerate(path_data):
            if i % 2 == 0:
                node = PathNodeData(uuid=vertex.get("uuid") or "", kind=vertex.get("kind") or "")
                hops.append(PathHopData(node=node, relationship_identifier=pending_identifier))
                pending_identifier = None
            else:
                pending_identifier = vertex.get("name") or ""
        depth = len(hops) - 1 if len(hops) > 1 else 0
        return PathData(hops=hops, depth=depth)
