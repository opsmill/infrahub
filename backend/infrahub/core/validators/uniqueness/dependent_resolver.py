from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from infrahub.core import registry

from .query import AffectedUniquenessDependentsQuery

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.constants import RelationshipDirection
    from infrahub.core.timestamp import Timestamp
    from infrahub.database import InfrahubDatabase


class UniquenessDependentResolverInterface(Protocol):
    """Resolve which nodes of a kind reference a set of changed peer nodes.

    A uniqueness path such as "owner__name" makes a kind's constraint depend on a peer kind's
    attribute; when the peer changes, the constrained nodes themselves are absent from the diff and
    must be resolved by traversal before they can be node-scoped.
    """

    async def resolve(
        self,
        node_kind: str,
        relationship_identifier: str,
        relationship_direction: RelationshipDirection,
        peer_uuids: list[str],
    ) -> set[str]: ...


class UniquenessDependentResolver:
    """Resolve which nodes of a kind reference changed peer nodes, for cross-kind uniqueness scoping."""

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

        The relationship is traversed in `relationship_direction`, so only the nodes on the
        constrained side of the peers are returned even when the peer kind is the node kind itself.
        Only relationships visible from this branch (its own, its base, and the global branch) are
        considered. The result is a superset of the truly-related nodes and is empty when no peer
        uuids are given or none are referenced.
        """
        if not peer_uuids:
            return set()
        query = await AffectedUniquenessDependentsQuery.init(
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
