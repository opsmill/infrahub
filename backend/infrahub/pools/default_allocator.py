from __future__ import annotations

from typing import TYPE_CHECKING, Any

from infrahub.core import registry
from infrahub.core.protocols import CoreNumberPool
from infrahub.exceptions import NodeNotFoundError, PoolExhaustedError, ValidationError
from infrahub.pools.allocator import PoolAllocator

if TYPE_CHECKING:
    from infrahub.core.attribute import BaseAttribute
    from infrahub.core.branch import Branch
    from infrahub.core.node import Node
    from infrahub.core.relationship.model import RelationshipManager
    from infrahub.database import InfrahubDatabase


class DefaultPoolAllocator(PoolAllocator):
    """Pool allocator for regular node creation. Allocates from number pools and IP/Prefix pools."""

    def __init__(self, db: InfrahubDatabase, branch: Branch) -> None:
        self.db = db
        self.branch = branch

    async def allocate_for_attribute(
        self,
        attribute: BaseAttribute,
        identifier: str,  # noqa: ARG002
    ) -> Any | None:
        """Allocate from pool if attribute references one."""
        if not attribute.from_pool:
            return None

        pool_id = attribute.from_pool.get("id")
        if not pool_id:
            return None

        try:
            number_pool = await registry.manager.get_one(
                db=self.db, id=pool_id, kind=CoreNumberPool, raise_on_error=True
            )
        except NodeNotFoundError as exc:
            raise ValidationError(
                {f"{attribute.name}.from_pool": f"The pool requested {attribute.from_pool} was not found."}
            ) from exc

        try:
            next_value = await number_pool.get_resource(  # type: ignore
                db=self.db, branch=self.branch, node=attribute.node, attribute=attribute.schema
            )
        except PoolExhaustedError as exc:
            raise ValidationError(
                {f"{attribute.name}.from_pool": f"The pool {number_pool.name.value} is exhausted."}
            ) from exc

        return next_value

    async def allocate_for_relationship(self, pool_relationship: RelationshipManager, identifier: str) -> Node | None:
        """Allocate from pool referenced by relationship."""
        pool = await pool_relationship.get_peer(db=self.db)
        if not pool:
            return None

        return await pool.get_resource(db=self.db, branch=self.branch, identifier=identifier)  # type: ignore
