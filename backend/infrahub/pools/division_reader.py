from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub_sdk.utils import is_valid_uuid

from infrahub.core.schema.relationship_schema import RelationshipSchema
from infrahub.pools.scope import AllocationScope, AllocationScopeResolver, Division

if TYPE_CHECKING:
    from infrahub.core.node import Node
    from infrahub.core.relationship.model import RelationshipManager
    from infrahub.database import InfrahubDatabase
    from infrahub.profiles.node_applier import NodeProfilesApplier


class NodeNumberPoolDivisionReader:
    """Read the division a node being written holds, reading from the database only what the node does not hold yet.

    A relationship element whose peers the node has not read is read once, a peer named by a human-friendly id or a
    default filter value is resolved to its node id, or refused as the save would refuse it when no node matches,
    and an attribute element takes the value the node's profiles give it, as the node will hold once it is saved.
    """

    def __init__(
        self, db: InfrahubDatabase, scope_resolver: AllocationScopeResolver, profiles_applier: NodeProfilesApplier
    ) -> None:
        self.db = db
        self.scope_resolver = scope_resolver
        self.profiles_applier = profiles_applier

    async def read(self, node: Node, scope: AllocationScope, pool_name: str, attribute_name: str) -> Division:
        """Return the division the node holds for the scope, on the schema the resolver reads.

        Raises:
            ValidationError: When the schema of the node's branch does not define a scope element on the node's
                kind, or when an attribute element does not hold a single scalar value.
            NodeNotFoundError: When a peer named by a human-friendly id or a default filter value does not exist.

        """
        element_fields = self.scope_resolver.element_fields(
            kind=node.get_kind(), scope=scope, pool=pool_name, attribute=attribute_name
        )
        attribute_names: list[str] = []
        for _, field in element_fields:
            if isinstance(field, RelationshipSchema):
                await self._resolve_peers(relationship=node.get_relationship(name=field.name))
            else:
                attribute_names.append(field.name)
        await self.profiles_applier.apply_attribute_values(node=node, attr_names=attribute_names)

        return Division.from_node(node=node, element_fields=element_fields, pool=pool_name, attribute=attribute_name)

    async def read_for_pool(self, node: Node, pool: Node, attribute_name: str) -> Division | None:
        """Return the division the node holds for the number pool's scope, or None when the pool has no scope.

        Raises:
            ValidationError: When the stored scope is malformed, when the schema of the node's branch does not define
                one of its elements on the node's kind, or when an attribute element does not hold a single scalar.
            NodeNotFoundError: When a peer named by a human-friendly id or a default filter value does not exist.

        """
        scope = AllocationScope.from_stored(value=pool.get_attribute("allocation_scope").value, pool=pool.get_id())
        if scope.is_empty:
            return None
        return await self.read(
            node=node, scope=scope, pool_name=str(pool.get_attribute("name").value), attribute_name=attribute_name
        )

    async def _resolve_peers(self, relationship: RelationshipManager) -> None:
        """Resolve the relationship's peers to node ids, reading the peers when the node has not read them.

        Raises:
            NodeNotFoundError: When a peer named by a human-friendly id or a default filter value does not exist.

        """
        for related in await relationship.get_relationships(db=self.db):
            if not related.peer_id or not is_valid_uuid(related.peer_id):
                await related.resolve(db=self.db)
            if related.peer_id and not is_valid_uuid(related.peer_id):
                # Reading the peer raises the error a write without a scope gets when it saves this peer.
                await related.get_peer(db=self.db)
