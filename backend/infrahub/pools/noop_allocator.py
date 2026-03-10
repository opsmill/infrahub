from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from infrahub.core.node import Node
    from infrahub.core.relationship.model import RelationshipManager
    from infrahub.core.schema import MainSchemaTypes

from infrahub.pools.allocator import PoolAllocator


class NoOpPoolAllocator(PoolAllocator):
    """Pool allocator that skips all allocations."""

    async def allocate_for_attribute(
        self,
        pool_relationship: RelationshipManager,  # noqa: ARG002
        target_schema: MainSchemaTypes,  # noqa: ARG002
        attribute_name: str,  # noqa: ARG002
        identifier: str,  # noqa: ARG002
    ) -> Any | None:
        return None

    async def allocate_for_relationship(self, pool_relationship: RelationshipManager, identifier: str) -> Node | None:  # noqa: ARG002
        return None
