from neo4j import AsyncGraphDatabase, AsyncSession

# from contextlib import asynccontextmanager
from neo4j.exceptions import ClientError

import infrahub.config as config

from .metrics import QUERY_READ_METRICS, QUERY_WRITE_METRICS

validated_database = {}


async def get_db():

    global validated_database  # pylint: disable=global-variable-not-assigned

    URI = f"{config.SETTINGS.database.protocol}://{config.SETTINGS.database.address}"
    driver = AsyncGraphDatabase.driver(URI, auth=(config.SETTINGS.database.username, config.SETTINGS.database.password))

    if config.SETTINGS.database.database not in validated_database:
        try:

            session = driver.session(database=config.SETTINGS.database.database)
            await session.run("SHOW TRANSACTIONS")
            validated_database[config.SETTINGS.database.database] = True

        except ClientError as exc:
            if "database does not exist" in exc.message:

                default_db = driver.session()
                await default_db.run(f"CREATE DATABASE {config.SETTINGS.database.database}")
            elif "Unable to get a routing table for database" in exc.message:

                default_db = driver.session()
                await default_db.run(f"CREATE DATABASE {config.SETTINGS.database.database}")

            else:
                raise

    return driver


# def get_db() -> Generator[Session, None, None]:
#     global validated_database

#     if config.SETTINGS.database.database not in validated_database:
#         try:
#             db = driver.session(database=config.SETTINGS.database.database)
#             results = db.run("SHOW TRANSACTIONS")
#             validated_database[config.SETTINGS.database.database] = True

#         except ClientError as exc:
#             if "database does not exist" in exc.message:

#                 default_db = driver.session()
#                 results = default_db.run(f"CREATE DATABASE {config.SETTINGS.database.database}")

#                 # TODO Catch possible exception here

#             else:
#                 raise

#     db = driver.session(database=config.SETTINGS.database.database)

#     # FIXME should be enclosed in try/finally block but somehow it is not working right now
#     yield db

#     db.close()


# @QUERY_READ_METRICS.time()
# def execute_read_query(query: str, params: dict = None, session: Session = None):

#     if not session:
#         session: Session = next(get_db())

#     response = session.run(query, params)
#     return list(response)


# @QUERY_WRITE_METRICS.time()
# def execute_write_query(query: str, params: dict = None, session: Session = None):

#     if not session:
#         session: Session = next(get_db())

#     response = session.run(query, params)
#     return list(response)


@QUERY_READ_METRICS.time()
async def execute_read_query_async(
    session: AsyncSession,
    query: str,
    params: dict = None,
):
    async def work(tx, params: dict):
        response = await tx.run(query, params)
        return [item async for item in response]

    return await session.execute_read(work, params)


@QUERY_WRITE_METRICS.time()
async def execute_write_query_async(session: AsyncSession, query: str, params: dict = None):
    async def work(tx, params: dict):
        response = await tx.run(query, params)
        return await response.values()

    return await session.execute_write(work, params)
