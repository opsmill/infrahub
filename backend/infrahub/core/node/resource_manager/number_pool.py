from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub import lock
from infrahub.core import registry
from infrahub.core.query.resource_manager import (
    NumberPoolGetFree,
    NumberPoolGetReserved,
    NumberPoolGetUsed,
    NumberPoolSetReserved,
)
from infrahub.core.schema.attribute_parameters import NumberAttributeParameters
from infrahub.exceptions import PoolExhaustedError

from .. import Node
from ..lock_utils import RESOURCE_POOL_LOCK_NAMESPACE

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.schema import AttributeSchema
    from infrahub.core.timestamp import Timestamp
    from infrahub.database import InfrahubDatabase


class CoreNumberPool(Node):
    _free_number_page_size_factor = 10

    def get_attribute_nb_excluded_values(self) -> int:
        """Returns the number of excluded values for the attribute of the number pool."""

        pool_node = registry.schema.get(name=self.node.value)  # type: ignore [attr-defined]
        attribute = [attribute for attribute in pool_node.attributes if attribute.name == self.node_attribute.value][0]  # type: ignore [attr-defined]
        if not isinstance(attribute.parameters, NumberAttributeParameters):
            return 0

        sum_excluded_values = 0
        excluded_ranges = attribute.parameters.get_excluded_ranges()
        for start_range, end_range in excluded_ranges:
            sum_excluded_values += end_range - start_range + 1

        res = len(attribute.parameters.get_excluded_single_values()) + sum_excluded_values
        return res

    async def get_used(
        self,
        db: InfrahubDatabase,
        branch: Branch,
    ) -> list[int]:
        """Returns a list of used numbers in the pool."""

        query = await NumberPoolGetUsed.init(db=db, branch=branch, pool=self, branch_agnostic=True)
        await query.execute(db=db)
        used = [result.value for result in query.iter_results()]
        return [item for item in used if item is not None]

    async def get_free(
        self,
        db: InfrahubDatabase,
        branch: Branch,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[int]:
        """Returns a list of free numbers in the pool."""

        query = await NumberPoolGetFree.init(
            db=db, branch=branch, pool=self, branch_agnostic=True, limit=limit, offset=offset
        )
        await query.execute(db=db)
        return list(query.iter_results())

    async def reserve(self, db: InfrahubDatabase, number: int, identifier: str, at: Timestamp | None = None) -> None:
        """Reserve a number in the pool for a specific identifier."""

        query = await NumberPoolSetReserved.init(
            db=db, pool_id=self.get_id(), identifier=identifier, reserved=number, at=at
        )
        await query.execute(db=db)

    async def get_resource(
        self,
        db: InfrahubDatabase,
        branch: Branch,
        node: Node,
        attribute: AttributeSchema,
        identifier: str | None = None,
        at: Timestamp | None = None,
    ) -> int:
        async with lock.registry.get(name=self.get_id(), namespace=RESOURCE_POOL_LOCK_NAMESPACE):
            # NOTE: ideally we should use the HFID as the identifier (if available)
            # one of the challenge with using the HFID is that it might change over time
            # so we need to ensure that the identifier is stable, or we need to handle the case where the identifier changes
            identifier = identifier or node.get_id()

            # Check if there is already a resource allocated with this identifier
            # if not, pull all existing number and allocate the next available
            # TODO add support for branch, if the node is reserved with this id in another branch we should return an error
            query_get = await NumberPoolGetReserved.init(db=db, branch=branch, pool_id=self.id, identifier=identifier)
            await query_get.execute(db=db)
            reservation = query_get.get_reservation()
            if reservation is not None:
                return reservation

            # If we have not returned a value we need to find one if avaiable
            number = await self.get_next(db=db, branch=branch, attribute=attribute)
            await self.reserve(db=db, number=number, identifier=identifier, at=at)
            return number

    async def get_next(self, db: InfrahubDatabase, branch: Branch, attribute: AttributeSchema) -> int:
        parameters = attribute.parameters if isinstance(attribute.parameters, NumberAttributeParameters) else None

        page_index = 0
        while True:
            free = await self.get_free(
                db=db,
                branch=branch,
                offset=page_index * self._free_number_page_size_factor,
                limit=self._free_number_page_size_factor,
            )
            if not free:
                raise PoolExhaustedError("There are no more values available in this pool.")

            for num in free:
                if parameters is None or parameters.is_valid_value(num):
                    return num

            page_index += 1

    async def get_next_many(
        self, db: InfrahubDatabase, quantity: int, branch: Branch, attribute: AttributeSchema
    ) -> list[int]:
        if quantity <= 0:
            return []

        allocated: list[int] = []
        allocated_set: set[int] = set()
        page_index = 0
        page_size = quantity * self._free_number_page_size_factor
        parameters = attribute.parameters if isinstance(attribute.parameters, NumberAttributeParameters) else None

        while len(allocated) < quantity:
            free = await self.get_free(
                db=db,
                branch=branch,
                offset=page_index * page_size,
                limit=page_size,
            )
            if not free:
                raise PoolExhaustedError(
                    f"There are no more values available in this pool, couldn't allocate {quantity} values, only {len(allocated)} available."
                )

            for number in free:
                if number in allocated_set:
                    continue
                if parameters is not None and not parameters.is_valid_value(number):
                    continue
                allocated.append(number)
                allocated_set.add(number)
                if len(allocated) == quantity:
                    break

            page_index += 1

        return allocated
