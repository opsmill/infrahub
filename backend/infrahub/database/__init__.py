from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Type

from neo4j import (
    READ_ACCESS,
    WRITE_ACCESS,
    AsyncDriver,
    AsyncGraphDatabase,
    AsyncSession,
    AsyncTransaction,
    Record,
)

# from contextlib import asynccontextmanager
from neo4j.exceptions import ClientError, ServiceUnavailable

from infrahub import config
from infrahub.exceptions import DatabaseError
from infrahub.log import get_logger
from infrahub.utils import InfrahubStringEnum

from .constants import DatabaseType
from .metrics import QUERY_EXECUTION_METRICS

if TYPE_CHECKING:
    from types import TracebackType

validated_database = {}

log = get_logger()


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


class InfrahubDatabaseSessionMode(InfrahubStringEnum):
    READ = "read"
    WRITE = "write"


class InfrahubDatabase:
    """Base class for database access"""

    def __init__(
        self,
        driver: AsyncDriver,
        mode: InfrahubDatabaseMode = InfrahubDatabaseMode.DRIVER,
        db_type: Optional[DatabaseType] = None,
        session: Optional[AsyncSession] = None,
        session_mode: InfrahubDatabaseSessionMode = InfrahubDatabaseSessionMode.WRITE,
        transaction: Optional[AsyncTransaction] = None,
    ):
        self._mode = mode
        self._driver = driver
        self._session = session
        self._session_mode = session_mode
        self._is_session_local = False
        self._transaction = transaction
        if db_type and isinstance(db_type, DatabaseType):
            self.db_type = db_type
        else:
            self.db_type = config.SETTINGS.database.db_type

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

    def start_session(self, read_only: bool = False) -> InfrahubDatabase:
        """Create a new InfrahubDatabase object in Session mode."""
        session_mode = InfrahubDatabaseSessionMode.WRITE
        if read_only:
            session_mode = InfrahubDatabaseSessionMode.READ

        return self.__class__(
            mode=InfrahubDatabaseMode.SESSION, db_type=self.db_type, driver=self._driver, session_mode=session_mode
        )

    def start_transaction(self) -> InfrahubDatabase:
        return self.__class__(
            mode=InfrahubDatabaseMode.TRANSACTION,
            db_type=self.db_type,
            driver=self._driver,
            session=self._session,
            session_mode=self._session_mode,
        )

    async def session(self) -> AsyncSession:
        if self._session:
            return self._session

        if self._session_mode == InfrahubDatabaseSessionMode.READ:
            self._session = self._driver.session(
                database=config.SETTINGS.database.database_name, default_access_mode=READ_ACCESS
            )
        else:
            self._session = self._driver.session(
                database=config.SETTINGS.database.database_name, default_access_mode=WRITE_ACCESS
            )

        self._is_session_local = True
        return self._session

    async def transaction(self) -> AsyncTransaction:
        if self._transaction:
            return self._transaction

        session = await self.session()
        self._transaction = await session.begin_transaction()
        return self._transaction

    async def __aenter__(self) -> InfrahubDatabase:
        if self._mode == InfrahubDatabaseMode.SESSION:
            if self._session_mode == InfrahubDatabaseSessionMode.READ:
                self._session = self._driver.session(
                    database=config.SETTINGS.database.database_name, default_access_mode=READ_ACCESS
                )
            else:
                self._session = self._driver.session(
                    database=config.SETTINGS.database.database_name, default_access_mode=WRITE_ACCESS
                )

            return self

        if self._mode == InfrahubDatabaseMode.TRANSACTION:
            session = await self.session()
            self._transaction = await session.begin_transaction()
            return self

    async def __aexit__(self, exc_type: Type[BaseException], exc_value: BaseException, traceback: TracebackType):
        if self._mode == InfrahubDatabaseMode.SESSION:
            return await self._session.close()

        if self._mode == InfrahubDatabaseMode.TRANSACTION:
            if exc_type is not None:
                await self._transaction.rollback()
            else:
                await self._transaction.commit()

            if self._is_session_local:
                await self._session.close()

    async def close(self):
        await self._driver.close()

    async def execute_query(
        self, query: str, params: Optional[Dict[str, Any]] = None, name: Optional[str] = "undefined"
    ) -> List[Record]:
        with QUERY_EXECUTION_METRICS.labels(str(self._session_mode), name).time():
            if self.is_transaction:
                execution_method = await self.transaction()
            else:
                execution_method = await self.session()

            try:
                response = await execution_method.run(query=query, parameters=params)
            except ServiceUnavailable as exc:
                log.error("Database Service unavailable", error=str(exc))
                raise DatabaseError(message="Unable to connect to the database") from exc

            return [item async for item in response]

    def render_list_comprehension(self, items: str, item_name: str) -> str:
        if self.db_type == DatabaseType.MEMGRAPH:
            return f"extract(i in {items} | i.{item_name})"
        return f"[i IN {items} | i.{item_name}]"


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
            await create_database(driver=driver, database_name=config.SETTINGS.database.database_name)

        if retry == 0:
            raise

        await asyncio.sleep(retry_interval)
        await validate_database(driver=driver, database_name=database_name, retry=retry - 1, create_db=False)

    return True


async def get_db(retry: int = 0) -> AsyncDriver:
    URI = f"{config.SETTINGS.database.protocol}://{config.SETTINGS.database.address}:{config.SETTINGS.database.port}"
    driver = AsyncGraphDatabase.driver(URI, auth=(config.SETTINGS.database.username, config.SETTINGS.database.password))

    if config.SETTINGS.database.database_name not in validated_database:
        await validate_database(
            driver=driver, database_name=config.SETTINGS.database.database_name, retry=retry, create_db=True
        )

    return driver


async def execute_read_query_async(
    db: InfrahubDatabase,
    query: str,
    params: Optional[Dict[str, Any]] = None,
    name: Optional[str] = "undefined",
) -> List[Record]:
    with QUERY_EXECUTION_METRICS.labels("read", name).time():
        if db.is_transaction:
            tx = await db.transaction()
            response = await tx.run(query=query, parameters=params or {})
            return [item async for item in response]

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
