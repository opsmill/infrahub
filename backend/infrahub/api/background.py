import asyncio
import os
import random

from fastapi.logger import logger
from neo4j import AsyncDriver, AsyncSession

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.lock import registry as lock_registry


class BackgroundRunner:
    def __init__(self, driver: AsyncDriver, database_name: str, interval: int = 10):
        self.driver = driver
        self.database_name = database_name
        self.interval = interval

    async def run(self):
        while True:
            async with self.driver.session(database=self.database_name) as session:
                await self.refresh_branches(session=session)

            # Add some randomness to the interval to avoid having all workers pulling the latest update at the same time
            random_number = random.randint(1, 4)
            await asyncio.sleep(self.interval + random_number - 2)

    async def refresh_branches(self, session: AsyncSession):
        """Pull all the branches from the database and update the registry.

        If a branch is already present with a different value for the hash
        We pull the new schema from the database and we update the registry.
        """

        async with lock_registry.get_branch_schema_update():
            logger.error(f"[{os.getpid()}] Runner: lock acquired")

            branches = await Branch.get_list(session=session)
            active_branches = [branch.name for branch in branches]
            for new_branch in branches:
                branch_already_present = new_branch.name in registry.branch

                if branch_already_present:
                    if registry.branch[new_branch.name].schema_hash != new_branch.schema_hash:
                        logger.error(
                            f"[{os.getpid()}] {new_branch.name}: New hash detected OLD {registry.branch[new_branch.name].schema_hash} >> {new_branch.schema_hash} NEW"
                        )
                        registry.branch[new_branch.name] = new_branch
                        await registry.schema.load_schema_from_db(session=session, branch=new_branch)

                else:
                    logger.error(f"[{os.getpid()}] {new_branch.name}: New branch detected")
                    registry.branch[new_branch.name] = new_branch
                    await registry.schema.load_schema_from_db(session=session, branch=new_branch)

            for branch_name, _ in registry.branch.items():
                if branch_name not in active_branches:
                    del registry.branch[branch_name]
                    logger.error(f"[{os.getpid()}]  Removed branch {branch_name} from the registry")
