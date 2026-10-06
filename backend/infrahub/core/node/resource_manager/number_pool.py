from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub import lock
from infrahub.core.query.resource_manager import PoolRecordProvenance
from infrahub.pools.number_pool_allocator import NumberPoolAllocator
from infrahub.pools.number_pool_repository import NumberPoolRepository

from .. import Node
from ..lock_utils import RESOURCE_POOL_LOCK_NAMESPACE

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.schema import AttributeSchema
    from infrahub.core.timestamp import Timestamp
    from infrahub.database import InfrahubDatabase


class CoreNumberPool(Node):
    """A pool hands out numbers through the resource pool contract every pool kind shares.

    That contract delivers the database per call, so each call builds the repository and the allocator
    before any work starts and runs the whole allocation on them.
    """

    async def get_resource(
        self,
        db: InfrahubDatabase,
        branch: Branch,
        attribute: AttributeSchema,
        identifier: str,
        attribute_id: str | None = None,
        at: Timestamp | None = None,
    ) -> int:
        repository = NumberPoolRepository(db=db)
        allocator = NumberPoolAllocator(numbers=repository)
        async with lock.registry.get(name=self.get_id(), namespace=RESOURCE_POOL_LOCK_NAMESPACE):
            # If the attribute already exists, try to get its pool reservation
            if attribute_id is not None:
                reservation = await repository.get_reservation(
                    pool_id=self.get_id(), branch=branch, identifier=identifier
                )
                if reservation is not None:
                    return reservation

            # If we have not returned a value we need to find one if avaiable
            number = await allocator.next_number(pool=self, branch=branch, attribute=attribute)
            if attribute_id is not None:
                # Cannot reserve without an Attribute to link
                await repository.reserve(
                    pool_id=self.get_id(),
                    identifier=identifier,
                    attribute_id=attribute_id,
                    provenance=PoolRecordProvenance.ALLOCATED,
                    at=at,
                )
            return number
