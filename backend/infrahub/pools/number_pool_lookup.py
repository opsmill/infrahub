from __future__ import annotations

from typing import TYPE_CHECKING, Literal, Protocol

from infrahub_sdk.utils import is_valid_uuid

from infrahub.core.constants import InfrahubKind
from infrahub.core.protocols import CoreNumberPool
from infrahub.exceptions import NodeNotFoundError

if TYPE_CHECKING:
    from collections.abc import Sequence

    from infrahub.database import InfrahubDatabase


class NumberPoolReader(Protocol):
    """Reads number pools by id, or by filters on their attributes."""

    async def get_one(
        self, id: str, db: InfrahubDatabase, kind: type[CoreNumberPool], raise_on_error: Literal[True]
    ) -> CoreNumberPool: ...

    async def query(
        self, db: InfrahubDatabase, schema: type[CoreNumberPool], filters: dict | None
    ) -> Sequence[CoreNumberPool]: ...


class NumberPoolLookup:
    """Find the number pool a write names, by its id or by its name."""

    def __init__(self, db: InfrahubDatabase, node_manager: NumberPoolReader) -> None:
        self.db = db
        self.node_manager = node_manager

    async def find(self, pool_ref: str) -> CoreNumberPool:
        """Return the number pool whose id or name is `pool_ref`.

        Raises:
            NodeNotFoundError: When no number pool has that id or name.

        """
        if is_valid_uuid(pool_ref):
            return await self.node_manager.get_one(id=pool_ref, db=self.db, kind=CoreNumberPool, raise_on_error=True)
        results = await self.node_manager.query(db=self.db, schema=CoreNumberPool, filters={"name__value": pool_ref})
        if not results:
            raise NodeNotFoundError(node_type=InfrahubKind.NUMBERPOOL, identifier=pool_ref)
        return results[0]
