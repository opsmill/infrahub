from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from infrahub.database import get_db

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase


@dataclass
class CliContext:
    database_class: type[InfrahubDatabase]
    application: str = "infrahub.server:app"

    async def get_db(self, retry: int = 0) -> InfrahubDatabase:
        return self.database_class(driver=await get_db(retry=retry))
