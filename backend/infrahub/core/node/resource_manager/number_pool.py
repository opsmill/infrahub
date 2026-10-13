from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub import lock
from infrahub.core.constants import SYSTEM_USER_ID
from infrahub.exceptions import ValidationError
from infrahub.pools.number_pool_number_picker import NumberPoolNumberPicker
from infrahub.pools.number_pool_repository import NumberPoolRepository
from infrahub.pools.scope import AllocationScope

from .. import Node
from ..lock_utils import RESOURCE_POOL_LOCK_NAMESPACE

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.schema import AttributeSchema
    from infrahub.core.timestamp import Timestamp
    from infrahub.database import InfrahubDatabase
    from infrahub.pools.scope import Division


class CoreNumberPool(Node):
    """A pool hands out numbers through the resource pool contract every pool kind shares.

    That contract delivers the database per call, so each call builds the repository and the number picker
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
        user_id: str = SYSTEM_USER_ID,
        division: Division | None = None,
    ) -> int:
        """Return the number reserved for `identifier`, or the next free one, within `division` when one is given.

        Raises:
            ValidationError: When a division is given to a pool that has no allocation scope.
            PoolExhaustedError: When the pool, or the division, has no number left to give.

        """
        repository = NumberPoolRepository(db=db)
        picker = NumberPoolNumberPicker(number_reader=repository)
        async with lock.registry.get(name=self._lock_name(division=division), namespace=RESOURCE_POOL_LOCK_NAMESPACE):
            # If the attribute already exists, try to get its pool reservation
            if attribute_id is not None:
                reservation = await repository.get_reservation(
                    pool_id=self.get_id(),
                    branch=branch,
                    identifier=identifier,
                    division=division,
                )
                if reservation is not None:
                    return reservation

            # If we have not returned a value we need to find one if avaiable
            number = await picker.next_number(pool=self, branch=branch, attribute=attribute, division=division)
            if attribute_id is not None:
                # Cannot reserve without an Attribute to link
                await repository.reserve(
                    pool_id=self.get_id(),
                    identifier=identifier,
                    attribute_id=attribute_id,
                    allocated_value=number,
                    at=at,
                    user_id=user_id,
                )
            return number

    def _lock_name(self, division: Division | None) -> str:
        """Return the pool id, followed by the division key when the pool is scoped, so each division locks apart.

        Raises:
            ValidationError: When a division is given to a pool that has no allocation scope.

        """
        if division is None:
            return self.get_id()
        scope = AllocationScope.from_stored(value=self.get_attribute("allocation_scope").value, pool=self.get_id())
        if scope.is_empty:
            raise ValidationError(f"The pool {self.get_id()} has no allocation scope; a division cannot be applied")
        return f"{self.get_id()}.{division.key}"
