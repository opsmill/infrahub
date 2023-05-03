import asyncio

from fastapi.logger import logger
from neo4j import AsyncDriver, AsyncSession

from infrahub.core import registry
from infrahub.core.branch import Branch


class BackgroundRunner:
    def __init__(self, driver: AsyncDriver, database_name: str, interval: int = 10):
        self.driver = driver
        self.database_name = database_name
        self.interval = interval

    async def run(self):
        while True:
            async with self.driver.session(database=self.database_name) as session:
                await self.refresh_branches(session=session)

            await asyncio.sleep(self.interval)

    async def refresh_branches(self, session: AsyncSession):
        """Pull all the branches from the database and update the registry.

        If a branch is already present with a different value for the hash
        We pull the new schema from the database and we update the registry.
        """
        branches = await Branch.get_list(session=session)
        active_branches = [branch.name for branch in branches]
        for new_branch in branches:
            if new_branch.name in registry.branch:
                if registry.branch[new_branch.name].schema_hash != new_branch.schema_hash:
                    logger.error(
                        f"{new_branch.name}: New hash detected {registry.branch[new_branch.name].schema_hash} >> {new_branch.schema_hash}"
                    )
                    await registry.schema.load_schema_from_db(session=session, branch=new_branch)

            registry.branch[new_branch.name] = new_branch

        for branch_name, branch in registry.branch.items():
            if branch_name not in active_branches:
                del registry.branch[branch_name]
                logger.error(f"Removed branch {branch_name} from the registry")

        # TODO check
