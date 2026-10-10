from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

from infrahub.core.constants import SYSTEM_USER_ID
from infrahub.core.query.resource_manager import (
    NumberPoolReleaseReserved,
    NumberPoolSetReserved,
)
from infrahub.exceptions import InitializationError

if TYPE_CHECKING:
    from infrahub.core.attribute import BaseAttribute
    from infrahub.core.branch import Branch
    from infrahub.core.node import Node
    from infrahub.core.protocols import CoreNumberPool
    from infrahub.core.schema import AttributeSchema
    from infrahub.core.timestamp import Timestamp
    from infrahub.database import InfrahubDatabase
    from infrahub.pools.scope import Division


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
        user_id: str = SYSTEM_USER_ID,
        division: Division | None = None,
    ) -> int: ...


class NumberPoolAttributeAllocator:
    """Draw a number for an attribute from a number pool, or have the pool start or stop tracking the number it holds."""

    def __init__(self, db: InfrahubDatabase) -> None:
        self.db = db

    async def allocate(
        self,
        pool: CoreNumberPool,
        node: Node,
        attribute: BaseAttribute,
        user_id: str,
        division: Division | None = None,
    ) -> int:
        """Return the number the pool holds for the attribute, or the next free one in `division` when one is given.

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
            user_id=user_id,
            division=division,
        )

    async def attach(self, pool: CoreNumberPool, node: Node, attribute: BaseAttribute, user_id: str) -> None:
        """Have the pool track the number the saved attribute already holds.

        Raises:
            InitializationError: When the attribute has not been saved yet.

        """
        if attribute.id is None:
            raise InitializationError(f"'{attribute.name}' must be saved before a pool can track it")
        query = await NumberPoolSetReserved.init(
            db=self.db,
            pool_id=pool.get_id(),
            identifier=node.get_id(),
            attribute_id=attribute.id,
            allocated_value=None,
            user_id=user_id,
        )
        await query.execute(db=self.db)

    async def release(self, attribute: BaseAttribute, user_id: str) -> None:
        """Have every pool stop tracking the saved attribute, which keeps the number it holds.

        Raises:
            InitializationError: When the attribute has not been saved yet.

        """
        if attribute.id is None:
            raise InitializationError(f"'{attribute.name}' must be saved before a pool can stop tracking it")
        query = await NumberPoolReleaseReserved.init(db=self.db, attribute_id=attribute.id, user_id=user_id)
        await query.execute(db=self.db)
