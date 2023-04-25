from __future__ import annotations

import asyncio
from typing import Optional

from neo4j import AsyncDriver, AsyncGraphDatabase, AsyncSession

# from contextlib import asynccontextmanager
from neo4j.exceptions import ClientError

import infrahub.config as config

from .metrics import QUERY_READ_METRICS, QUERY_WRITE_METRICS

validated_database = {}


async def validate_database(driver: AsyncDriver, database_name: str, retry: int = 0, retry_interval: int = 1) -> bool:
    """Validate if a database is present in Neo4j by executing a simple query.

    Args:
        driver (AsyncDriver): Neo4j Driver
        database_name (str): Name of the database in Neo4j
        retry (int, optional): Number of retry before raising an exception. Defaults to 0.
        retry_interval (int, optional): Time between retries in second. Defaults to 1.
    """

    try:
        session = driver.session(database=database_name)
        await session.run("SHOW TRANSACTIONS")
        validated_database[database_name] = True
    except ClientError:
        if retry == 0:
            raise

        await asyncio.sleep(retry_interval)
        validated_database(driver=driver, database_name=database_name, retry=retry - 1)

    return True


async def get_db():
    global validated_database  # pylint: disable=global-variable-not-assigned

    URI = f"{config.SETTINGS.database.protocol}://{config.SETTINGS.database.address}"
    driver = AsyncGraphDatabase.driver(URI, auth=(config.SETTINGS.database.username, config.SETTINGS.database.password))

    if config.SETTINGS.database.database not in validated_database:
        try:
            await validate_database(driver=driver, database_name=config.SETTINGS.database.database)

        except ClientError as exc:
            if "database does not exist" in exc.message or "Unable to get a routing table for database" in exc.message:
                default_db = driver.session()
                await default_db.run(f"CREATE DATABASE {config.SETTINGS.database.database}")
                await validate_database(driver=driver, database_name=config.SETTINGS.database.database, retry=3)
            else:
                raise

    return driver


@QUERY_READ_METRICS.time()
async def execute_read_query_async(
    session: AsyncSession,
    query: str,
    params: Optional[dict] = None,
):
    async def work(tx, params: dict):
        response = await tx.run(query, params)
        return [item async for item in response]

    return await session.execute_read(work, params)


@QUERY_WRITE_METRICS.time()
async def execute_write_query_async(session: AsyncSession, query: str, params: Optional[dict] = None):
    async def work(tx, params: dict):
        response = await tx.run(query, params)
        return await response.values()

    return await session.execute_write(work, params)
