from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from infrahub.core.query import Query, QueryType
from infrahub.graph_traversal._cypher import render_plan_to_cypher
from infrahub.graph_traversal._extract import extract_path_from_result
from infrahub.graph_traversal.results import PathData, PathNodeData

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase
    from infrahub.graph_traversal.planning.models import Plan


@dataclass(frozen=True)
class ReachableNodeData:
    node: PathNodeData
    depth: int
    path: PathData


class ReachableNodesQuery(Query):
    """Render a pre-built ``Plan`` (with a ``TerminalByKinds`` predicate) into Cypher and execute it."""

    name = "reachable_nodes_discovery"
    type = QueryType.READ
    insert_return = False
    insert_limit = False

    def __init__(
        self,
        *,
        plan: Plan,
        source_id: str,
        default_branch_name: str,
        max_results: int = 50,
        **kwargs: Any,
    ) -> None:
        if plan.is_empty:
            raise ValueError("ReachableNodesQuery requires a non-empty plan")

        self.plan = plan
        self.source_id = source_id
        self.default_branch_name = default_branch_name
        self.max_results = max_results

        super().__init__(**kwargs)

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        rendered = render_plan_to_cypher(
            plan=self.plan,
            source_id=self.source_id,
            branch=self.branch,
            default_branch_name=self.default_branch_name,
            at=self.at,
            max_results=self.max_results,
        )
        self.add_to_query(rendered.text)
        self.params.update(rendered.params)
        self.return_labels = list(rendered.return_labels)

    def get_reachable_nodes(self) -> list[ReachableNodeData]:
        results: list[ReachableNodeData] = []
        for result in self.get_results():
            path = extract_path_from_result(result)
            if path is None or not path.hops:
                continue
            terminal = path.hops[-1].node
            results.append(
                ReachableNodeData(
                    node=PathNodeData(uuid=terminal.uuid, kind=terminal.kind),
                    depth=path.depth,
                    path=path,
                )
            )
        return results
