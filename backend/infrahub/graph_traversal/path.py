from __future__ import annotations

from typing import TYPE_CHECKING, Any

from infrahub.core.query import Query, QueryType
from infrahub.graph_traversal._extract import extract_path_from_result

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase
    from infrahub.graph_traversal._cypher import GraphTraversalCypherRenderer
    from infrahub.graph_traversal.planning.models import Plan
    from infrahub.graph_traversal.results import PathData


class PathTraversalQuery(Query):
    """Execute a traversal plan and project the shortest matched paths."""

    name = "path_traversal"
    type = QueryType.READ
    insert_return = False
    insert_limit = False

    def __init__(
        self,
        *,
        renderer: GraphTraversalCypherRenderer,
        plan: Plan,
        source_id: str,
        max_paths: int,
        **kwargs: Any,
    ) -> None:
        self._renderer = renderer
        self._plan = plan
        self._source_id = source_id
        self._max_paths = max_paths
        super().__init__(**kwargs)

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        rendered = self._renderer.render_shortest_path_by_id(
            plan=self._plan,
            source_id=self._source_id,
            at=self.at,
            max_paths=self._max_paths,
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
