from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from infrahub.core.attribute import BaseAttribute
    from infrahub.core.node import Node
    from infrahub.core.relationship.model import RelationshipManager

from infrahub.pools.allocator import PoolAllocator


class NoOpPoolAllocator(PoolAllocator):
    """Pool allocator that skips all allocations."""

    async def allocate_for_attribute(self, attribute: BaseAttribute, identifier: str) -> Any | None:  # noqa: ARG002
        return None

    async def allocate_for_relationship(self, pool_relationship: RelationshipManager, identifier: str) -> Node | None:  # noqa: ARG002
        return None
