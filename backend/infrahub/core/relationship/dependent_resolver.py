from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from infrahub.core import registry
from infrahub.core.query.dependent_nodes import DependentNodesQuery

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.constants import RelationshipDirection
    from infrahub.core.timestamp import Timestamp
    from infrahub.database import InfrahubDatabase


class DependentNodeResolverInterface(Protocol):
    """Resolve which nodes of a kind reference a set of peer nodes through a relationship.

    When a peer is changed it is present in a diff, but the nodes that reach it through a relationship
    are not; they have to be resolved by traversal before they can be acted on node by node.
    """

    async def resolve(
        self,
        node_kind: str,
        relationship_identifier: str,
        relationship_direction: RelationshipDirection,
        peer_uuids: list[str],
    ) -> set[str]: ...


class DependentNodeResolver:
    """Resolve which nodes of a kind reference peer nodes through a named relationship."""

    def __init__(self, db: InfrahubDatabase, branch: Branch, at: Timestamp | str | None = None) -> None:
        self.db = db
        self.branch = branch
        self.at = at

    async def resolve(
        self,
        node_kind: str,
        relationship_identifier: str,
        relationship_direction: RelationshipDirection,
        peer_uuids: list[str],
    ) -> set[str]:
        """Return the uuids of `node_kind` nodes related via `relationship_identifier` to any peer in `peer_uuids`.

        The relationship is traversed in `relationship_direction`, so only the nodes on the owning
        side of the peers are returned even when the peer kind is the node kind itself. Only
        relationships visible from this branch (its own, its base, and the global branch) are
        considered. The result is a superset of the truly-related nodes and is empty when no peer
        uuids are given or none are referenced.
        """
        if not peer_uuids:
            return set()
        query = await DependentNodesQuery.init(
            db=self.db,
            branch=self.branch,
            at=self.at,
            node_kind=node_kind,
            relationship_identifier=relationship_identifier,
            relationship_direction=relationship_direction,
            peer_uuids=peer_uuids,
            default_branch_name=registry.default_branch,
        )
        await query.execute(db=self.db)
        return query.get_dependent_uuids()
