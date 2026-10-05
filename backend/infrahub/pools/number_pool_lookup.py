from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub_sdk.utils import is_valid_uuid

from infrahub.core import registry
from infrahub.core.constants import InfrahubKind
from infrahub.core.protocols import CoreNumberPool
from infrahub.exceptions import NodeNotFoundError

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase


class NumberPoolLookup:
    """Find the number pool a write names, by its id or by its name."""

    def __init__(self, db: InfrahubDatabase) -> None:
        self.db = db

    async def find(self, pool_ref: str) -> CoreNumberPool:
        """Return the number pool whose id or name is `pool_ref`.

        Raises:
            NodeNotFoundError: When no number pool has that id or name.

        """
        if is_valid_uuid(pool_ref):
            return await registry.manager.get_one(db=self.db, id=pool_ref, kind=CoreNumberPool, raise_on_error=True)
        results = await registry.manager.query(db=self.db, schema=CoreNumberPool, filters={"name__value": pool_ref})
        if not results:
            raise NodeNotFoundError(node_type=InfrahubKind.NUMBERPOOL, identifier=pool_ref)
        return results[0]
