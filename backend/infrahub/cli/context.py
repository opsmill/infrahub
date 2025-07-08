from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from infrahub.workers.dependencies import get_database

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase


@dataclass
class CliContext:
    application: str = "infrahub.server:app"

    # This method is inherited for Infrahub Enterprise.
    @staticmethod
    async def init_db(retry: int) -> InfrahubDatabase:  # type:ignore  # noqa
        return await get_database()
