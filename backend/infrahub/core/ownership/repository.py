from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core.constants.database import DatabaseEdgeType
from infrahub.core.query.node import NodeUpdateMetadataQuery

from .constants import NO_OWNER_VERTEX_UUID
from .models import NODE_HOLDER, NODE_SOURCES_HOLDER, HolderKey, StoredNodeOwnership, StoredOwnerState
from .queries import (
    NodeLabelsReadQuery,
    NodeOwnerEdgesCloseQuery,
    NodeOwnerStateReadQuery,
    OwnerStateWriteQuery,
    parent_relationships_by_kind,
)
from .sources import SOURCE_EDGE_TYPE, NodeSourcesWriteQuery, stored_sources

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.timestamp import Timestamp
    from infrahub.database import InfrahubDatabase


def _stored_state(held: tuple[tuple[str, str], ...], known: StoredOwnerState | None) -> StoredOwnerState:
    """Return the owner state that the active owner edges of a holder give.

    Args:
        held: The type and the peer ID of each edge.
        known: The state of another vertex with the same key, which a merge of two branches can leave.

    """
    # Owner edges win over a "no owner" edge that a merge leaves active.
    owner_ids = {
        peer_id
        for edge_type, peer_id in held
        if edge_type == DatabaseEdgeType.HAS_OWNER.value and peer_id != NO_OWNER_VERTEX_UUID
    }
    template_ids = [peer_id for edge_type, peer_id in held if edge_type == DatabaseEdgeType.HAS_OWNER_SOURCE.value]
    if known is not None:
        owner_ids.update(known.owner_ids or ())
        template_ids.extend([known.template_id] if known.template_id else [])
    return StoredOwnerState(owner_ids=tuple(sorted(owner_ids)), template_id=min(template_ids, default=None))


class OwnershipRepository:
    """Read and write the owner states that the graph stores, as one branch reads them."""

    def __init__(self, db: InfrahubDatabase, branch: Branch, at: Timestamp | None) -> None:
        """Set `at` to None to read at the time of each call."""
        self.db = db
        self.branch = branch
        self.at = at
        self._parent_by_kind: dict[str, dict[str, str]] | None = None

    async def read(
        self, node_ids: list[str], attributes: bool = False, lineage: bool = False
    ) -> dict[str, StoredNodeOwnership]:
        """Return the stored owner states, the sources, the parent and the profiles of each active node.

        A node is active when it exists at the read time.

        Args:
            node_ids: The nodes to read.
            attributes: True to read the states of the attributes of each node also.
            lineage: True to return also the parents above each node and the profiles that give them owners, as far
                as the query finds them.

        """
        if not node_ids:
            return {}
        if self._parent_by_kind is None:
            self._parent_by_kind = parent_relationships_by_kind(
                schema_branch=self.db.schema.get_schema_branch(name=self.branch.name)
            )
        query = await NodeOwnerStateReadQuery.init(
            db=self.db,
            branch=self.branch,
            at=self.at,
            node_ids=node_ids,
            parent_by_kind=self._parent_by_kind,
            attributes=attributes,
            lineage=lineage,
        )
        await query.execute(db=self.db)
        stored: dict[str, StoredNodeOwnership] = {}
        for row in query.get_data():
            holders: dict[HolderKey, StoredOwnerState] = {}
            if sources := stored_sources(held=row.held):
                holders[NODE_SOURCES_HOLDER] = sources
            owner_held = tuple(edge for edge in row.held if edge[0] != SOURCE_EDGE_TYPE)
            for holder, held in ((NODE_HOLDER, owner_held), *row.field_holders):
                # The mark of a copy from an object template gives no state without an owner edge.
                if any(edge_type != DatabaseEdgeType.HAS_OWNER_SOURCE.value for edge_type, _ in held):
                    holders[holder] = _stored_state(held=held, known=holders.get(holder))
            stored[row.node_id] = StoredNodeOwnership(
                node_id=row.node_id, kind=row.kind, holders=holders, parent_id=row.parent_id, profiles=row.profiles
            )
        return stored

    async def write(
        self,
        node_id: str,
        holder: HolderKey,
        state: StoredOwnerState,
        write_branch: Branch,
        at: Timestamp,
        user_id: str,
        skip_inactive: bool = False,
        keep_deleted_owners: bool = False,
    ) -> bool:
        """Replace the owner state of one holder, or the sources of the node for the holder of the sources.

        Args:
            write_branch: The branch that gets the edge changes: the global branch for a node that all branches share.
            skip_inactive: Write nothing, and raise no error, when the node is not active at the write time.
            keep_deleted_owners: True to also write an edge to an owner that is deleted at the write time, for a copy
                of a list that the graph stores. A write of a list that a user gives keeps the default, which skips
                such an owner.

        Returns:
            False when the node is not active at the write time, else True.

        Raises:
            QueryError: When the node is not active at the write time, and `skip_inactive` is False.

        """
        query_class = NodeSourcesWriteQuery if holder == NODE_SOURCES_HOLDER else OwnerStateWriteQuery
        query = await query_class.init(
            db=self.db,
            branch=self.branch,
            at=at,
            user_id=user_id,
            node_id=node_id,
            holder=holder,
            owner_ids=list(state.owner_ids) if state.owner_ids is not None else None,
            template_id=state.template_id,
            write_branch=write_branch,
            keep_deleted_owners=keep_deleted_owners,
        )
        query.raise_error_if_empty = not skip_inactive
        await query.execute(db=self.db)
        return bool(query.results)

    async def record_node_update(self, node_id: str, write_branch: Branch, at: Timestamp, user_id: str) -> None:
        """Record the time and the author of an update on the node vertex.

        The vertex holds them for the default and the global branch only, so another write branch changes nothing.
        """
        if not (write_branch.is_default or write_branch.is_global):
            return
        query = await NodeUpdateMetadataQuery.init(
            db=self.db, branch=write_branch, node_id=node_id, user_id=user_id, at=at
        )
        await query.execute(db=self.db)

    async def close_node_owner_edges(self, node_id: str, write_branch: Branch, at: Timestamp, user_id: str) -> None:
        """Close the owner edges and the source edges of a node that a delete removes.

        The owner edges include the owners that the node gives to its nodes. A node that is not active keeps its
        edges.
        """
        query = await NodeOwnerEdgesCloseQuery.init(
            db=self.db,
            branch=self.branch,
            at=at,
            user_id=user_id,
            node_id=node_id,
            holder=NODE_HOLDER,
            owner_ids=None,
            write_branch=write_branch,
        )
        await query.execute(db=self.db)

    async def read_labels(self, node_ids: list[str]) -> dict[str, set[str]]:
        """Return the labels of each node that is active at the read time."""
        if not node_ids:
            return {}
        query = await NodeLabelsReadQuery.init(db=self.db, branch=self.branch, at=self.at, node_ids=node_ids)
        await query.execute(db=self.db)
        return query.get_labels()
