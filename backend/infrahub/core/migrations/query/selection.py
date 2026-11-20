from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar

from infrahub.core.query import Query, QueryType

if TYPE_CHECKING:
    from collections.abc import Sequence

    from infrahub.database import InfrahubDatabase


class MigrationSelectionQuery(Query):
    """A migration query whose write runs on a selection of nodes that can also be counted on its own.

    The write and the count render the same selection with the same parameters, so the count matches
    the nodes the write changes. The selection opens with ``render_node_match()`` so that the node scope applies.
    """

    selected_node: ClassVar[str] = "active_node"

    def __init__(self, node_ids: frozenset[str] | list[str] | None = None, **kwargs: Any) -> None:
        self.node_ids: tuple[str, ...] | None = None if node_ids is None else tuple(node_ids)
        super().__init__(**kwargs)
        if self.node_ids is not None:
            self.params["node_ids"] = list(self.node_ids)

    def render_node_match(self, variable: str, labels: Sequence[str], conditions: Sequence[str] = ()) -> str:
        """Return the ``MATCH`` that opens the selection on the nodes with one of `labels`, within the node scope if any.

        The scoped form carries an index hint because the planner otherwise chooses where the query starts from its
        statistics, which can start from a scan of the labels instead of a seek on the node IDs.
        """
        label_expression = "|".join(labels)
        filters = [f"({condition})" for condition in conditions]
        if self.node_ids is None:
            lines = [f"MATCH ({variable}:{label_expression})"]
        else:
            lines = [
                f"MATCH ({variable}:Node&({label_expression}))",
                f"USING INDEX SEEK {variable}:Node(uuid)",
            ]
            filters.insert(0, f"{variable}.uuid IN $node_ids")
        if filters:
            lines.append("WHERE " + " AND ".join(filters))
        return "\n".join(lines)

    def render_selection(self) -> str:
        """Return the Cypher that selects the nodes to change, ending with ``selected_node`` in scope.

        Raises:
            NotImplementedError: When the subclass does not define its selection.

        """
        raise NotImplementedError

    async def count_changes(self, db: InfrahubDatabase) -> dict[str, int]:
        """Return the number of distinct selected nodes per node kind, without running the write.

        The query must be built with ``init()``, because the selection reads the parameters it sets.
        """
        node = self.selected_node
        query = self.render_selection() + f"\nRETURN {node}.kind AS kind, count(DISTINCT {node}) AS nbr"
        results = await db.execute_query(
            query=query, params=self.params, name=f"{self.name}_count", type=QueryType.READ
        )
        return {result["kind"]: result["nbr"] for result in results}
