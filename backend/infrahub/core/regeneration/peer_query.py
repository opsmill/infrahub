from __future__ import annotations

from typing import TYPE_CHECKING, Any

from infrahub.core.constants import BranchSupportType
from infrahub.core.manager import NodeManager

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase


class RelationshipPeerQuery:
    """Run a relationship's peer query on a branch, as the GraphQL resolver does."""

    def __init__(self, *, db: InfrahubDatabase, branch: Branch, schema_branch: SchemaBranch) -> None:
        self._db = db
        self._branch = branch
        self._schema_branch = schema_branch

    async def read(
        self,
        *,
        owner_kind: str,
        relationship_name: str,
        owner_ids: Sequence[str],
        peer_ids: Sequence[str],
        filters: Mapping[str, Any],
    ) -> set[tuple[str, str]]:
        """Return the (owner, peer) pairs the read returns with ``filters``, among ``owner_ids`` and ``peer_ids``."""
        if not owner_ids or not peer_ids:
            return set()
        relationship = self._schema_branch.get(name=owner_kind, duplicate=False).get_relationship(
            name=relationship_name
        )
        query_filters = dict(filters)
        # A read that selects peers by id keeps its own id filter, and the returned pairs are limited to ``peer_ids``.
        if not {f"{relationship_name}__id", f"{relationship_name}__ids"} & query_filters.keys():
            query_filters[f"{relationship_name}__ids"] = list(peer_ids)
        returned = await NodeManager.query_peers(
            db=self._db,
            ids=list(owner_ids),
            source_kind=owner_kind,
            schema=relationship,
            filters=query_filters,
            branch=self._branch,
            branch_agnostic=relationship.branch is BranchSupportType.AGNOSTIC,
        )
        wanted = set(peer_ids)
        return {(peer.node_id, peer.get_peer_id()) for peer in returned if peer.get_peer_id() in wanted}
