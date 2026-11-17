from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from infrahub.core.query import Query, QueryType

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase


class MigrationSelectionQuery(Query):
    """A migration query whose write runs on a selection of nodes that can also be counted on its own.

    The write and the count render the same selection with the same parameters, so the count matches
    the nodes the write changes.
    """

    selected_node: ClassVar[str] = "active_node"

    def render_selection(self) -> str:
        """Return the Cypher that selects the nodes to change, ending in a ``WITH`` that names ``selected_node``.

        Raises:
            NotImplementedError: When the subclass does not define its selection.

        """
        raise NotImplementedError

    async def count_changes(self, db: InfrahubDatabase) -> dict[str, int]:
        """Return the number of distinct selected nodes per node kind, without running the write."""
        node = self.selected_node
        query = self.render_selection() + f"\nRETURN {node}.kind AS kind, count(DISTINCT {node}) AS nbr"
        results = await db.execute_query(
            query=query, params=self.params, name=f"{self.name}_count", type=QueryType.READ
        )
        return {result["kind"]: result["nbr"] for result in results}
