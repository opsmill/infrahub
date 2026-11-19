from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar

from infrahub.core.query import Query, QueryType

if TYPE_CHECKING:
    from collections.abc import Sequence

    from infrahub.core.timestamp import Timestamp
    from infrahub.database import InfrahubDatabase


class MigrationSelectionQuery(Query):
    """A migration query whose write runs on a selection of nodes that can also be counted on its own.

    The write and the count render the same selection with the same parameters, so the count matches
    the nodes the write changes.
    """

    selected_node: ClassVar[str] = "active_node"

    def __init__(self, operation_ats: Sequence[Timestamp] = (), **kwargs: Any) -> None:
        self.operation_ats = list(operation_ats)
        super().__init__(**kwargs)

    @property
    def operation_ats_param(self) -> list[str]:
        """Return the timestamps of the operation this write belongs to, its own included, as strings.

        A vertex last stamped at one of them was already changed by this operation, so its previous stamp
        is the one from before the operation and is kept.
        """
        return list(dict.fromkeys([at.to_string() for at in self.operation_ats] + [self.at.to_string()]))

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
