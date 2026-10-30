from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core.constants import SYSTEM_USER_ID
from infrahub.pools.number_pool_locker import NumberPoolLock
from infrahub.pools.number_pool_number_picker import NumberPoolNumberPicker
from infrahub.pools.number_pool_repository import NumberPoolRepository

from .. import Node

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.schema import AttributeSchema
    from infrahub.core.timestamp import Timestamp
    from infrahub.database import InfrahubDatabase
    from infrahub.pools.scope import Division


class CoreNumberPool(Node):
    """A pool hands out numbers through the resource pool contract every pool kind shares.

    That contract delivers the database per call, so each call builds the repository, the number picker and the
    pool locker before any work starts and runs the whole allocation on them.
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
        reuse_reservation: bool = True,
    ) -> int:
        """Return the number reserved for `identifier`, or the next free one, within `division` when one is given.

        Without `reuse_reservation` the reserved number is ignored and the next free one is returned.

        Raises:
            ValidationError: When a division is given to a pool that has no allocation scope.
            PoolExhaustedError: When the pool, or the division, has no number left to give.

        """
        repository = NumberPoolRepository(db=db)
        picker = NumberPoolNumberPicker(number_reader=repository)
        locker = NumberPoolLock(db=db)
        # The picking lock comes first, as in a mutation, so a range change never waits on a holder queued behind it.
        async with locker.picking(pool=self, division=division), locker.holding(pool_id=self.get_id()):
            if attribute_id is not None and reuse_reservation:
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
                await repository.reserve(
                    pool_id=self.get_id(),
                    identifier=identifier,
                    attribute_id=attribute_id,
                    allocated_value=number,
                    at=at,
                    user_id=user_id,
                )
            return number
