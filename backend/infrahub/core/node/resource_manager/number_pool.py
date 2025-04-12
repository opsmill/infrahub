from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core.query.resource_manager import NumberPoolGetReserved, NumberPoolGetUsed, NumberPoolSetReserved
from infrahub.exceptions import PoolExhaustedError

from .. import Node

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase


class CoreNumberPool(Node):
    async def get_resource(
        self,
        db: InfrahubDatabase,
        branch: Branch,
        node: Node,
        identifier: str | None = None,
    ) -> int:
        identifier = identifier or node.get_id()
        # Check if there is already a resource allocated with this identifier
        # if not, pull all existing prefixes and allocated the next available
        # TODO add support for branch, if the node is reserved with this id in another branch we should return an error
        query_get = await NumberPoolGetReserved.init(db=db, branch=branch, pool_id=self.id, identifier=identifier)
        await query_get.execute(db=db)
        reservation = query_get.get_reservation()
        if reservation is not None:
            return reservation

        # If we have not returned a value we need to find one if avaiable
        number = await self.get_next(db=db, branch=branch)

        query_set = await NumberPoolSetReserved.init(
            db=db, pool_id=self.get_id(), identifier=identifier, reserved=number
        )
        await query_set.execute(db=db)

        return number

    async def get_next(self, db: InfrahubDatabase, branch: Branch) -> int:
        query = await NumberPoolGetUsed.init(db=db, branch=branch, pool=self, branch_agnostic=True)
        await query.execute(db=db)
        taken = [result.get_as_optional_type("av.value", return_type=int) for result in query.results]
        next_number = find_next_free(
            start=self.start_range.value,  # type: ignore[attr-defined]
            end=self.end_range.value,  # type: ignore[attr-defined]
            taken=taken,
        )
        if next_number is None:
            raise PoolExhaustedError("There are no more values available in this pool.")

        return next_number


def find_next_free(start: int, end: int, taken: list[int | None]) -> int | None:
    used_numbers = [number for number in taken if number is not None]
    used_set = set(used_numbers)

    for num in range(start, end + 1):
        if num not in used_set:
            return num

    return None
