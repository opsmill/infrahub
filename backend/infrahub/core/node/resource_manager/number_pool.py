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
        self, db: InfrahubDatabase, branch: Branch, min_value: int | None = None, max_value: int | None = None
    ) -> int | None:
        """Returns the next free number in the pool.

        Args:
            db: Database connection.
            branch: Branch to query.
            min_value: Minimum value to start searching from.
            max_value: Maximum value to search up to.

        Returns:
            The next free number, or None if no free numbers are available.
        """

        query = await NumberPoolGetFree.init(
            db=db, branch=branch, pool=self, branch_agnostic=True, min_value=min_value, max_value=max_value
        )
        await query.execute(db=db)

        return query.get_result_value()

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
        attribute: AttributeSchema,
        identifier: str,
        at: Timestamp | None = None,
    ) -> int:
        async with lock.registry.get(name=self.get_id(), namespace=RESOURCE_POOL_LOCK_NAMESPACE):
            # NOTE: ideally we should use the HFID as the identifier (if available)
            # one of the challenge with using the HFID is that it might change over time
            # so we need to ensure that the identifier is stable, or we need to handle the case where the identifier changes

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
        """Get the next available number from the pool.

        Args:
            db: Database connection.
            branch: Branch to query.
            attribute: Attribute schema that may contain NumberAttributeParameters constraints.

        Returns:
            The next available number that satisfies all constraints.

        Raises:
            PoolExhaustedError: If no valid numbers are available in the pool.
        """
        parameters = attribute.parameters if isinstance(attribute.parameters, NumberAttributeParameters) else None

        # Extract exclusion constraints from the attribute parameters
        excluded_values: set[int] = set()
        excluded_ranges: list[tuple[int, int]] = []

        if parameters:
            excluded_values = set(parameters.get_excluded_single_values())
            excluded_ranges = parameters.get_excluded_ranges()

        # Compute effective range by combining pool range with min/max constraints
        pool_start = self.start_range.value  # type: ignore[attr-defined]
        pool_end = self.end_range.value  # type: ignore[attr-defined]

        effective_start = pool_start
        effective_end = pool_end

        if parameters:
            if parameters.min_value is not None:
                effective_start = max(effective_start, parameters.min_value)
            if parameters.max_value is not None:
                effective_end = min(effective_end, parameters.max_value)

        # Check if the effective range is valid
        if effective_start > effective_end:
            raise PoolExhaustedError("There are no more values available in this pool.")

        def skip_excluded(value: int) -> int | None:
            """Skip past any excluded values/ranges starting from value.

            Returns the next non-excluded value, or None if we exceed effective_end.
            """
            current = value
            while current <= effective_end:
                # Check if in an excluded range and skip past it
                in_range = False
                for range_start, range_end in excluded_ranges:
                    if range_start <= current <= range_end:
                        current = range_end + 1
                        in_range = True
                        break
                if in_range:
                    continue

                # Check if it's an excluded single value
                if current in excluded_values:
                    current += 1
                    continue

                # Found a non-excluded value
                return current

            return None

        # Skip any excluded values at the start
        first_valid = skip_excluded(effective_start)
        if first_valid is None:
            raise PoolExhaustedError("There are no more values available in this pool.")
        min_value = first_valid

        # Re-run the query until we find a non-excluded value or exhaust the pool
        while True:
            candidate = await self.get_free(db=db, branch=branch, min_value=min_value, max_value=effective_end)
            if candidate is None:
                raise PoolExhaustedError("There are no more values available in this pool.")

            # Check if candidate is excluded (single value or range)
            next_valid = skip_excluded(candidate)
            if next_valid is None:
                raise PoolExhaustedError("There are no more values available in this pool.")

            if next_valid != candidate:
                # Candidate was excluded, re-query starting from next valid point
                min_value = next_valid
                continue

            # Candidate passed all checks
            return candidate
