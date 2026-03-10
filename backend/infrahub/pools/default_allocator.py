from __future__ import annotations

from typing import TYPE_CHECKING, Any

from infrahub.core.creation_context import NodeCreationContext
from infrahub.pools.allocator import PoolAllocator

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.node import Node
    from infrahub.core.relationship.model import RelationshipManager
    from infrahub.core.schema import MainSchemaTypes
    from infrahub.database import InfrahubDatabase


class DefaultPoolAllocator(PoolAllocator):
    """Pool allocator for regular node creation. Allocates from number pools and IP/Prefix pools."""

    def __init__(self, db: InfrahubDatabase, branch: Branch) -> None:
        self.db = db
        self.branch = branch

    async def allocate_for_attribute(
        self,
        pool_relationship: RelationshipManager,
        target_schema: MainSchemaTypes,
        attribute_name: str,
        identifier: str,
    ) -> Any | None:
        """Allocate from a _from_resource_pool relationship for an attribute (Number → CoreNumberPool)."""
        pool = await pool_relationship.get_peer(db=self.db)
        if not pool:
            return None

        attr_schema = target_schema.get_attribute(name=attribute_name)
        # NumberPool.get_resource needs a node-like object for identifier; use identifier directly
        return await pool.get_resource(db=self.db, branch=self.branch, identifier=identifier, attribute=attr_schema)  # type: ignore[attr-defined]

    async def allocate_for_relationship(self, pool_relationship: RelationshipManager, identifier: str) -> Node | None:
        """Allocate from pool referenced by relationship."""
        pool = await pool_relationship.get_peer(db=self.db)
        if not pool:
            return None

        allocated = await pool.get_resource(db=self.db, branch=self.branch, identifier=identifier)  # type: ignore
        if allocated:
            NodeCreationContext.record_if_active(node=allocated)
        return allocated
