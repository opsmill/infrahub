from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub import lock
from infrahub.core import registry
from infrahub.core.query.resource_manager import PoolRecordProvenance
from infrahub.core.schema.attribute_parameters import NumberAttributeParameters
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

    def get_attribute_nb_excluded_values(self) -> int:
        """Returns the number of excluded values for the attribute of the number pool."""
        pool_node = registry.schema.get(name=self.node.value)  # type: ignore [attr-defined]
        attribute = next(attribute for attribute in pool_node.attributes if attribute.name == self.node_attribute.value)  # type: ignore [attr-defined]
        if not isinstance(attribute.parameters, NumberAttributeParameters):
            return 0

        sum_excluded_values = 0
        excluded_ranges = attribute.parameters.get_excluded_ranges()
        for start_range, end_range in excluded_ranges:
            sum_excluded_values += end_range - start_range + 1

        return len(attribute.parameters.get_excluded_single_values()) + sum_excluded_values

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
