from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from infrahub.core.node import Node
    from infrahub.core.relationship.model import RelationshipManager
    from infrahub.core.schema import MainSchemaTypes


class PoolAllocator(ABC):
    """Interface for pool allocation strategies."""

    @abstractmethod
    async def allocate_for_attribute(
        self,
        pool_relationship: RelationshipManager,
        target_schema: MainSchemaTypes,
        attribute_name: str,
        identifier: str,
    ) -> Any | None:
        """Allocate from a _from_resource_pool relationship for an attribute (e.g., Number → CoreNumberPool)."""

    @abstractmethod
    async def allocate_for_relationship(self, pool_relationship: RelationshipManager, identifier: str) -> Node | None:
        """Allocate from resource pool for a _from_resource_pool relationship."""
