from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING

from infrahub.core.constants import InfrahubKind

if TYPE_CHECKING:
    from infrahub.core.changelog.models import NodeChangelog
    from infrahub.core.node import Node

INTERNAL_GROUP_TYPE = "internal"
QUERY_GROUP_TRACKING_RELATIONSHIPS = frozenset({"members", "subscribers", "query"})


def is_internal_query_group(node: Node) -> bool:
    """Return whether the node is a GraphQL query group that Infrahub maintains to track what a stored query read."""
    if node.get_kind() != InfrahubKind.GRAPHQLQUERYGROUP:
        return False
    group_type = node.get_attribute("group_type").value
    if isinstance(group_type, Enum):
        group_type = group_type.value
    return group_type == INTERNAL_GROUP_TYPE


def changelog_for_peer_events(node: Node, changelog: NodeChangelog) -> NodeChangelog:
    """Return the part of the changelog whose relationship changes emit an update event on each peer.

    An internal query group records every node a stored query read, so its members, subscribers and
    query get no event of their own when that record changes.
    """
    if not is_internal_query_group(node):
        return changelog
    return changelog.model_copy(
        update={
            "relationships": {
                name: relationship
                for name, relationship in changelog.relationships.items()
                if name not in QUERY_GROUP_TRACKING_RELATIONSHIPS
            }
        }
    )
