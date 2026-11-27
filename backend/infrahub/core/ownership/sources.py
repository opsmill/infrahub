"""The sources of a node: one `HAS_SOURCE` edge from the node vertex to each source."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from infrahub.core.constants.database import DatabaseEdgeType

from .models import StoredOwnerState
from .queries import ActiveEdgeFilter, OwnerStateWriteQuery

if TYPE_CHECKING:
    from collections.abc import Iterable

SOURCE_EDGE_TYPE = DatabaseEdgeType.HAS_SOURCE.value


def stored_sources(held: Iterable[tuple[str, str]]) -> StoredOwnerState | None:
    """Return the sources that the active edges of a node vertex give, and None when the node has no source.

    Args:
        held: The type and the peer ID of each edge.

    """
    source_ids = sorted(peer_id for edge_type, peer_id in held if edge_type == SOURCE_EDGE_TYPE)
    return StoredOwnerState(owner_ids=tuple(source_ids)) if source_ids else None


class NodeSourcesWriteQuery(OwnerStateWriteQuery):
    """Replace the sources of an active node, given as `owner_ids`. Without source, the node keeps no source edge."""

    name = "ownership_node_sources_write"
    closed_edge_types = SOURCE_EDGE_TYPE
    listed_edge_type = SOURCE_EDGE_TYPE

    def __init__(self, owner_ids: list[str] | None, **kwargs: Any) -> None:
        # An empty list of owners is the "no owner" state, which sources do not have.
        super().__init__(owner_ids=owner_ids or None, **kwargs)

    def _holders_query(self, branch_filter: str) -> str:  # noqa: ARG002
        return "WITH n, n AS h"


class SourceFilter(ActiveEdgeFilter):
    """Build the Cypher of the source filter of a list of nodes of one kind."""

    params_prefix = "source_filter_"

    def render(self, kind: str, source_ids: list[str], bound: bool) -> tuple[str, dict[str, Any]]:
        """Return the Cypher that binds `n` one time to each node that has one of the sources, and its parameters.

        The Cypher checks that the source edges are active. It does not check that `n` and the sources are active.

        Args:
            kind: The kind of the nodes of the list.
            source_ids: The sources to look for.
            bound: True when the query already binds `n`. Else the Cypher starts from the sources, so its cost
                follows the number of nodes of the sources, not the number of nodes of the kind.

        """
        _, params = self.branch.get_query_filter_path(at=self.at, params_prefix=self.params_prefix)
        params[f"{self.params_prefix}ids"] = source_ids
        active = self._active("sourced", f"(n)-[%s:{SOURCE_EDGE_TYPE}]->(source)")
        if bound:
            match = f"MATCH (n)-[sourced:{SOURCE_EDGE_TYPE}]->(source:Node)"
        else:
            # Without the hint, the planner can scan the index of all node IDs, or start from all nodes of the kind.
            match = f"MATCH (source:Node)<-[sourced:{SOURCE_EDGE_TYPE}]-(n:{kind})\nUSING INDEX SEEK source:Node(uuid)"
        query = f"""
{match}
WHERE source.uuid IN ${self.params_prefix}ids AND {active}
WITH DISTINCT n
"""
        return query, params
