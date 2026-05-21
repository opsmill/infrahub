from __future__ import annotations

from typing import TYPE_CHECKING, Any

from infrahub.core.query import Query, QueryType
from infrahub.graph_traversal._cypher import render_plan_to_cypher
from infrahub.graph_traversal._extract import extract_path_from_result

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase
    from infrahub.graph_traversal.planning.models import Plan
    from infrahub.graph_traversal.results import PathData


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
            path = extract_path_from_result(result)
            if path is not None:
                paths.append(path)
        return paths
