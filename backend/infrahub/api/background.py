import asyncio
import random

from fastapi.logger import logger

from infrahub.database import InfrahubDatabase
from infrahub.tasks.registry import refresh_branches


class BackgroundRunner:
    def __init__(self, db: InfrahubDatabase, database_name: str, interval: int = 10):
        self.db = db
        self.database_name = database_name
        self.interval = interval

    async def run(self):
        logger.info("Background process started")

        while True:
            # Add some randomness to the interval to avoid having all workers pulling the latest update at the same time
            random_number = random.randint(1, 4)
            await asyncio.sleep(self.interval + random_number - 2)

            async with self.db.start_session() as db:
                await refresh_branches(db=db)
