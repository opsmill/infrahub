from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Type

from neo4j import (
    AsyncDriver,
    AsyncGraphDatabase,
    AsyncSession,
    AsyncTransaction,
    Record,
)

# from contextlib import asynccontextmanager
from neo4j.exceptions import ClientError

import infrahub.config as config
from infrahub.utils import InfrahubStringEnum

from .metrics import QUERY_EXECUTION_METRICS

if TYPE_CHECKING:
    from types import TracebackType

validated_database = {}


class InfrahubDriver:
    def __init__(self, driver):
        self.driver = driver

    async def __aenter__(self):
        raise NotImplementedError

    async def __aexit__(self, exc_type: Type[BaseException], exc_value: BaseException, traceback: TracebackType):
        raise NotImplementedError


class InfrahubSession:
    def __init__(self, driver: InfrahubDriver):
        self.driver = driver

    async def __aenter__(self):
        raise NotImplementedError

    async def __aexit__(self, exc_type: Type[BaseException], exc_value: BaseException, traceback: TracebackType):
        raise NotImplementedError


class InfrahubTransaction:
    def __init__(self, driver: InfrahubDriver, session: InfrahubSession):
        self.driver = driver
        self.session = session

    async def __aenter__(self):
        raise NotImplementedError

    async def __aexit__(self, exc_type: Type[BaseException], exc_value: BaseException, traceback: TracebackType):
        raise NotImplementedError


class InfrahubDatabaseMode(InfrahubStringEnum):
    DRIVER = "driver"
    SESSION = "session"
    TRANSACTION = "transaction"


class InfrahubDatabase:
    """Base class for database access"""

    def __init__(
        self,
        driver: AsyncDriver,
        mode: InfrahubDatabaseMode = InfrahubDatabaseMode.DRIVER,
        session: Optional[AsyncSession] = None,
        transaction: Optional[AsyncTransaction] = None,
    ):
        self._mode = mode
        self._driver = driver
        self._session = session
        self._transaction = transaction

    # @classmethod
    # async def init(cls, driver: AsyncDriver, mode: InfrahubDatabaseMode = InfrahubDatabaseMode.DRIVER,  session: Optional[AsyncSession] = None) -> InfrahubDatabase:

    #     if mode == InfrahubDatabaseMode.SESSION:
    #         session = driver.session(database=config.SETTINGS.database.database)
    #         return cls(type=type, driver=driver, session=session)

    #     if mode == InfrahubDatabaseMode.TRANSACTION:
    #         transaction = await session.begin_transaction()
    #         return cls(type=type, driver=driver, session=session, transaction=transaction)

    #     return cls(type=type, driver=driver)

    @property
    def is_session(self):
        if self._mode == InfrahubDatabaseMode.SESSION:
            return True
        return False

    @property
    def is_transaction(self):
        if self._mode == InfrahubDatabaseMode.TRANSACTION:
            return True
        return False

    def start_session(self) -> InfrahubDatabase:
        return self.__class__(mode=InfrahubDatabaseMode.SESSION, driver=self._driver)

    def start_transaction(self) -> InfrahubDatabase:
        return self.__class__(mode=InfrahubDatabaseMode.TRANSACTION, driver=self._driver, session=self._session)

    async def session(self) -> AsyncSession:
        if self._session:
            return self._session

        self._session = self._driver.session(database=config.SETTINGS.database.database)
        return self._session

    def new_session(self) -> AsyncSession:
        return self._driver.session(database=config.SETTINGS.database.database)

    async def transaction(self) -> AsyncTransaction:
        if self._transaction:
            return self._transaction

        session = await self.session()
        self._transaction = await session.begin_transaction()
        return self._transaction

    async def __aenter__(self) -> InfrahubDatabase:
        if self._mode == InfrahubDatabaseMode.SESSION:
            self._session = self._driver.session(database=config.SETTINGS.database.database)
            return self

        if self._mode == InfrahubDatabaseMode.TRANSACTION:
            session = await self.session()
            self._transaction = await session.begin_transaction()
            return self

    async def __aexit__(self, exc_type: Type[BaseException], exc_value: BaseException, traceback: TracebackType):
        if self._mode == InfrahubDatabaseMode.SESSION:
            return await self._session.close()

        if self._mode == InfrahubDatabaseMode.TRANSACTION:
            await self._transaction.commit()
            await self._session.close()

    async def close(self):
        await self._driver.close()


async def create_database(driver: AsyncDriver, database_name: str) -> None:
    default_db = driver.session()
    await default_db.run(f"CREATE DATABASE {database_name} WAIT")


async def validate_database(
    driver: AsyncDriver, database_name: str, retry: int = 0, retry_interval: int = 1, create_db: bool = True
) -> bool:
    """Validate if a database is present in Neo4j by executing a simple query.

    Args:
        driver (AsyncDriver): Neo4j Driver
        database_name (str): Name of the database in Neo4j
        retry (int, optional): Number of retry before raising an exception. Defaults to 0.
        retry_interval (int, optional): Time between retries in second. Defaults to 1.
    """
    global validated_database  # pylint: disable=global-variable-not-assigned

    try:
        session = driver.session(database=database_name)
        await session.run("SHOW TRANSACTIONS")
        validated_database[database_name] = True

    except ClientError as exc:
        if create_db and exc.code == "Neo.ClientError.Database.DatabaseNotFound":
            await create_database(driver=driver, database_name=config.SETTINGS.database.database)

        if retry == 0:
            raise

        await asyncio.sleep(retry_interval)
        await validate_database(driver=driver, database_name=database_name, retry=retry - 1, create_db=False)

    return True


async def get_db(retry: int = 0) -> AsyncDriver:
    URI = f"{config.SETTINGS.database.protocol}://{config.SETTINGS.database.address}:{config.SETTINGS.database.port}"
    driver = AsyncGraphDatabase.driver(URI, auth=(config.SETTINGS.database.username, config.SETTINGS.database.password))

    if config.SETTINGS.database.database not in validated_database:
        await validate_database(
            driver=driver, database_name=config.SETTINGS.database.database, retry=retry, create_db=True
        )

    return driver


async def execute_read_query_async(
    db: InfrahubDatabase,
    query: str,
    params: Optional[Dict[str, Any]] = None,
    name: Optional[str] = "undefined",
) -> List[Record]:
    with QUERY_EXECUTION_METRICS.labels("read", name).time():
        session = await db.session()
        response = await session.run(query=query, parameters=params or {})
        return [item async for item in response]


async def execute_write_query_async(
    query: str, db: InfrahubDatabase, params: Optional[Dict[str, Any]] = None, name: Optional[str] = "undefined"
) -> List[Record]:
    with QUERY_EXECUTION_METRICS.labels("write", name).time():
        if db.is_transaction:
            tx = await db.transaction()
            response = await tx.run(query=query, parameters=params or {})
            return [item async for item in response]

        session = await db.session()
        response = await session.run(query=query, parameters=params or {})
        return [item async for item in response]
