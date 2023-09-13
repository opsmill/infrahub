import asyncio
import random

from fastapi.logger import logger
from neo4j import AsyncDriver

from infrahub.tasks.registry import refresh_branches


class BackgroundRunner:
    def __init__(self, driver: AsyncDriver, database_name: str, interval: int = 10):
        self.driver = driver
        self.database_name = database_name
        self.interval = interval

    async def run(self):
        logger.info("Background process started")

        while True:
            async with self.driver.session(database=self.database_name) as session:
                await refresh_branches(session=session)

            # Add some randomness to the interval to avoid having all workers pulling the latest update at the same time
            random_number = random.randint(1, 4)
            await asyncio.sleep(self.interval + random_number - 2)
