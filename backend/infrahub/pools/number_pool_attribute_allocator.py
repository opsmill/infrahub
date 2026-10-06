from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

from infrahub.exceptions import InitializationError

if TYPE_CHECKING:
    from infrahub.core.attribute import BaseAttribute
    from infrahub.core.branch import Branch
    from infrahub.core.node import Node
    from infrahub.core.protocols import CoreNumberPool
    from infrahub.core.schema import AttributeSchema
    from infrahub.core.timestamp import Timestamp
    from infrahub.database import InfrahubDatabase


@runtime_checkable
class _AllocatingNumberPool(Protocol):
    async def get_resource(
        self,
        db: InfrahubDatabase,
        branch: Branch,
        attribute: AttributeSchema,
        identifier: str,
        attribute_id: str | None = None,
        at: Timestamp | None = None,
    ) -> int: ...


class NumberPoolAttributeAllocator:
    """Draw a number for an attribute from a number pool."""

    def __init__(self, db: InfrahubDatabase) -> None:
        self.db = db

    async def allocate(self, pool: CoreNumberPool, node: Node, attribute: BaseAttribute) -> int:
        """Return the number the pool holds for the attribute, or the next free one.

        Raises:
            InitializationError: When the pool was not loaded as a number pool that can allocate.
            PoolExhaustedError: When the pool has no number left to give.

        """
        if not isinstance(pool, _AllocatingNumberPool):
            raise InitializationError(f"The number pool {pool.get_id()} cannot allocate numbers")
        return await pool.get_resource(
            db=self.db,
            branch=node.get_branch(),
            identifier=node.get_id(),
            attribute=attribute.schema,
            attribute_id=attribute.id,
        )
