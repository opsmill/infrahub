from __future__ import annotations

from dataclasses import dataclass

from infrahub.database import InfrahubDatabase, get_db


@dataclass
class CliContext:
    application: str = "infrahub.server:app"

    # This method is inherited for Infrahub Enterprise.
    @staticmethod
    async def init_db(retry: int) -> InfrahubDatabase:
        return InfrahubDatabase(driver=await get_db(retry=retry))
