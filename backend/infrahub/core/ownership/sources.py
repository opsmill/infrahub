"""The sources of a node: one `HAS_SOURCE` edge from the node vertex to each source."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from infrahub.core.constants.database import DatabaseEdgeType

from .models import StoredOwnerState
from .queries import OwnerStateWriteQuery

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
