from __future__ import annotations

import uuid
from asyncio import Lock as LocalLock
from asyncio import sleep
from typing import Optional

import redis.asyncio as redis
from redis.asyncio.lock import Lock as DistributedLock

from infrahub import config

registry: InfrahubLock = None


class InfrahubLock:
    def __init__(self, token: Optional[str] = None):
        self.connection = redis.Redis(
            host=config.SETTINGS.cache.address,
            port=config.SETTINGS.cache.service_port,
            db=config.SETTINGS.cache.database,
        )

        self.token = token or str(uuid.uuid4())
        self.local_locks = {}

    def get_local(self, name: str) -> LocalLock:
        if name not in self.local_locks:
            self.local_locks[name] = LocalLock()
        return self.local_locks[name]

    def get(self, name: str) -> DistributedLock:
        return DistributedLock(redis=self.connection, name=name)

    async def wait_until_available(self, name: str) -> None:
        """Wait until a given lock is available.

        This allow to block functions what shouldnt process during an event
        but it's not a blocker if multiple of them happen at the same time.
        """
        while self.get(name=name).locked():
            await sleep(0.1)

    async def wait_until_local_available(self, name: str) -> None:
        """Wait until a given lock is available.

        This allow to block functions what shouldnt process during an event
        but it's not a blocker if multiple of them happen at the same time.
        """
        while self.get_local(name=name).locked():
            await sleep(0.1)

    def get_branch_schema_update(self) -> LocalLock:
        return self.get(name="branch-schema-update")

    async def wait_branch_schema_update_available(self) -> None:
        await self.wait_until_local_available(name="branch-schema-update")


def initialize_lock():
    global registry  # pylint: disable=global-statement
    registry = InfrahubLock()
