from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from infrahub.core.branch import Branch

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase

RESUME_TIMEOUT_SECONDS = 30


class PausedBranchList:
    """Branch lookups whose first list read, once it has read the database, waits until the test resumes it."""

    def __init__(self) -> None:
        self.read = asyncio.Event()
        self.resume = asyncio.Event()

    async def get_list(self, db: InfrahubDatabase, **kwargs: Any) -> list[Branch]:
        branches = await Branch.get_list(db=db, **kwargs)
        if not self.read.is_set():
            self.read.set()
            await asyncio.wait_for(self.resume.wait(), timeout=RESUME_TIMEOUT_SECONDS)
        return branches

    async def get_by_name(self, name: str, db: InfrahubDatabase) -> Branch:
        return await Branch.get_by_name(name=name, db=db)
