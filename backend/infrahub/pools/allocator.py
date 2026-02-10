from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from infrahub.core.attribute import BaseAttribute
    from infrahub.core.node import Node
    from infrahub.core.relationship.model import RelationshipManager


class PoolAllocator(ABC):
    """Interface for pool allocation strategies."""

    @abstractmethod
    async def allocate_for_attribute(self, attribute: BaseAttribute, identifier: str) -> Any | None:
        """Allocate from pool for an attribute (e.g. NumberPool)."""

    @abstractmethod
    async def allocate_for_relationship(self, pool_relationship: RelationshipManager, identifier: str) -> Node | None:
        """Allocate from resource pool for a _from_resource_pool relationship."""
