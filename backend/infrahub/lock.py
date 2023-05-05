from __future__ import annotations

from asyncio import Lock, sleep
from dataclasses import dataclass, field


@dataclass
class Registry:
    locks: dict = field(default_factory=dict)

    def get(self, name: str) -> Lock:
        if name not in self.locks:
            self.locks[name] = Lock()
        return self.locks[name]

    async def wait_until_available(self, name: str) -> None:
        """Wait until a given lock is available.

        This allow to block functions what shouldnt process during an event but it's not a blocker if multiple of them happen at the same time.
        """
        while self.get(name=name).locked():
            await sleep(0.1)

    def get_branch_schema_update(self) -> Lock:
        return self.get(name="branch-schema-update")

    async def wait_branch_schema_update_available(self) -> None:
        await self.wait_until_available(name="branch-schema-update")


registry = Registry()
