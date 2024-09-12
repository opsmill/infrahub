from __future__ import annotations

import asyncio
import random
from typing import TYPE_CHECKING, Any, Optional, Union

from neo4j import (
    READ_ACCESS,
    WRITE_ACCESS,
    AsyncDriver,
    AsyncGraphDatabase,
    AsyncResult,
    AsyncSession,
    AsyncTransaction,
    NotificationDisabledCategory,
    NotificationMinimumSeverity,
    Query,
    Record,
    TrustAll,
    TrustCustomCAs,
    TrustSystemCAs,
)
from neo4j.exceptions import ClientError, Neo4jError, ServiceUnavailable, TransientError
from opentelemetry import trace
from typing_extensions import Self

from infrahub import config, lock
from infrahub.core import registry
from infrahub.exceptions import DatabaseError
from infrahub.log import get_logger
from infrahub.utils import InfrahubStringEnum

from .constants import DatabaseType
from .memgraph import DatabaseManagerMemgraph
from .metrics import QUERY_EXECUTION_METRICS, TRANSACTION_RETRIES
from .neo4j import DatabaseManagerNeo4j

if TYPE_CHECKING:
    from types import TracebackType

    from infrahub.core.branch import Branch
    from infrahub.core.schema import MainSchemaTypes, NodeSchema
    from infrahub.core.schema_manager import SchemaBranch

    from .manager import DatabaseManager

validated_database = {}

log = get_logger()


class InfrahubDatabaseMode(InfrahubStringEnum):
    DRIVER = "driver"
    SESSION = "session"
    TRANSACTION = "transaction"


class InfrahubDatabaseSessionMode(InfrahubStringEnum):
    READ = "read"
    WRITE = "write"


def get_branch_name(branch: Optional[Union[Branch, str]] = None) -> str:
    if not branch:
        return registry.default_branch
    if isinstance(branch, str):
        return branch

    return branch.name


class DatabaseSchemaManager:
    def __init__(self, db: InfrahubDatabase):
        self._db = db

    def get(self, name: str, branch: Optional[Union[Branch, str]] = None, duplicate: bool = True) -> MainSchemaTypes:
        branch_name = get_branch_name(branch=branch)
        if branch_name not in self._db._schemas:
            return registry.schema.get(name=name, branch=branch, duplicate=duplicate)
        return self._db._schemas[branch_name].get(name=name, duplicate=duplicate)

    def get_node_schema(
        self, name: str, branch: Optional[Union[Branch, str]] = None, duplicate: bool = True
    ) -> NodeSchema:
        schema = self.get(name=name, branch=branch, duplicate=duplicate)
        if schema.is_node_schema:
            return schema

        raise ValueError("The selected node is not of type NodeSchema")

    def set(self, name: str, schema: MainSchemaTypes, branch: Optional[str] = None) -> int:
        branch_name = get_branch_name(branch=branch)
        if branch_name not in self._db._schemas:
            return registry.schema.set(name=name, schema=schema, branch=branch)
        return self._db._schemas[branch_name].set(name=name, schema=schema)

    def has(self, name: str, branch: Optional[Union[Branch, str]] = None) -> bool:
        branch_name = get_branch_name(branch=branch)
        if branch_name not in self._db._schemas:
            return registry.schema.has(name=name, branch=branch)
        return self._db._schemas[branch_name].has(name=name)

    def get_full(
        self, branch: Optional[Union[Branch, str]] = None, duplicate: bool = True
    ) -> dict[str, MainSchemaTypes]:
        branch_name = get_branch_name(branch=branch)
        if branch_name not in self._db._schemas:
            return registry.schema.get_full(branch=branch)
        return self._db._schemas[branch_name].get_all(duplicate=duplicate)

    async def get_full_safe(
        self, branch: Optional[Union[Branch, str]] = None, duplicate: bool = True
    ) -> dict[str, MainSchemaTypes]:
        await lock.registry.local_schema_wait()
        return self.get_full(branch=branch, duplicate=duplicate)

    def get_schema_branch(self, name: str) -> SchemaBranch:
        if name not in self._db._schemas:
            return registry.schema.get_schema_branch(name=name)
        return self._db._schemas[name]


class InfrahubDatabase:
    """Base class for database access"""

    def __init__(
        self,
        driver: AsyncDriver,
        mode: InfrahubDatabaseMode = InfrahubDatabaseMode.DRIVER,
        db_type: Optional[DatabaseType] = None,
        db_manager: Optional[DatabaseManager] = None,
        schemas: Optional[list[SchemaBranch]] = None,
        session: Optional[AsyncSession] = None,
        session_mode: InfrahubDatabaseSessionMode = InfrahubDatabaseSessionMode.WRITE,
        transaction: Optional[AsyncTransaction] = None,
    ):
        self._mode: InfrahubDatabaseMode = mode
        self._driver: AsyncDriver = driver
        self._session: Optional[AsyncSession] = session
        self._session_mode: InfrahubDatabaseSessionMode = session_mode
        self._is_session_local: bool = False
        self._transaction: Optional[AsyncTransaction] = transaction

        if schemas:
            self._schemas: dict[str, SchemaBranch] = {schema.name: schema for schema in schemas}
        else:
            self._schemas = {}
        self.schema: DatabaseSchemaManager = DatabaseSchemaManager(db=self)

        if db_type and isinstance(db_type, DatabaseType):
            self.db_type = db_type
        else:
            self.db_type = config.SETTINGS.database.db_type

        if db_manager:
            self.manager = db_manager
            self.manager.db = self
        elif self.db_type == DatabaseType.NEO4J:
            self.manager = DatabaseManagerNeo4j(db=self)
        elif self.db_type == DatabaseType.MEMGRAPH:
            self.manager = DatabaseManagerMemgraph(db=self)

    @property
    def is_session(self) -> bool:
        if self._mode == InfrahubDatabaseMode.SESSION:
            return True
        return False

    @property
    def is_transaction(self) -> bool:
        if self._mode == InfrahubDatabaseMode.TRANSACTION:
            return True
        return False

    def add_schema(self, schema: SchemaBranch, name: Optional[str] = None) -> None:
        self._schemas[name or schema.name] = schema

    def start_session(self, read_only: bool = False, schemas: Optional[list[SchemaBranch]] = None) -> InfrahubDatabase:
        """Create a new InfrahubDatabase object in Session mode."""
        session_mode = InfrahubDatabaseSessionMode.WRITE
        if read_only:
            session_mode = InfrahubDatabaseSessionMode.READ

        return self.__class__(
            mode=InfrahubDatabaseMode.SESSION,
            db_type=self.db_type,
            schemas=schemas or self._schemas.values(),
            db_manager=self.manager,
            driver=self._driver,
            session_mode=session_mode,
        )

    def start_transaction(self, schemas: Optional[list[SchemaBranch]] = None) -> InfrahubDatabase:
        return self.__class__(
            mode=InfrahubDatabaseMode.TRANSACTION,
            db_type=self.db_type,
            schemas=schemas or self._schemas.values(),
            db_manager=self.manager,
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

    async def transaction(self, name: Optional[str]) -> AsyncTransaction:
        if self._transaction:
            return self._transaction

        session = await self.session()
        self._transaction = await session.begin_transaction(
            metadata={"name": name, "infrahub_id": f"{trace.get_current_span().get_span_context().span_id:x}"}
        )
        return self._transaction

    async def __aenter__(self) -> Self:
        if self._mode == InfrahubDatabaseMode.SESSION:
            if self._session_mode == InfrahubDatabaseSessionMode.READ:
                self._session = self._driver.session(
                    database=config.SETTINGS.database.database_name, default_access_mode=READ_ACCESS
                )
            else:
                self._session = self._driver.session(
                    database=config.SETTINGS.database.database_name, default_access_mode=WRITE_ACCESS
                )

        elif self._mode == InfrahubDatabaseMode.TRANSACTION:
            session = await self.session()
            self._transaction = await session.begin_transaction()

        return self

    async def __aexit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc_value: Optional[BaseException],
        traceback: Optional[TracebackType],
    ):
        if self._mode == InfrahubDatabaseMode.SESSION:
            return await self._session.close()

        if self._mode == InfrahubDatabaseMode.TRANSACTION:
            if exc_type is not None:
                await self._transaction.rollback()
            else:
                try:
                    await self._transaction.commit()
                except Neo4jError as exc:
                    raise exc
                finally:
                    await self._transaction.close()

            if self._is_session_local:
                await self._session.close()

    async def close(self) -> None:
        await self._driver.close()

    async def execute_query(
        self, query: str, params: Optional[dict[str, Any]] = None, name: Optional[str] = "undefined"
    ) -> list[Record]:
        with trace.get_tracer(__name__).start_as_current_span("execute_db_query") as span:
            span.set_attribute("query", query)
            if name:
                span.set_attribute("query_name", name)

            with QUERY_EXECUTION_METRICS.labels(self._session_mode.value, name).time():
                response = await self.run_query(query=query, params=params)
                return [item async for item in response]

    async def execute_query_with_metadata(
        self, query: str, params: Optional[dict[str, Any]] = None, name: Optional[str] = "undefined"
    ) -> tuple[list[Record], dict[str, Any]]:
        with trace.get_tracer(__name__).start_as_current_span("execute_db_query_with_metadata") as span:
            span.set_attribute("query", query)
            if name:
                span.set_attribute("query_name", name)

            with QUERY_EXECUTION_METRICS.labels(self._session_mode.value, name).time():
                response = await self.run_query(query=query, params=params, name=name)
                results = [item async for item in response]
                return results, response._metadata or {}

    async def run_query(
        self, query: str, params: Optional[dict[str, Any]] = None, name: Optional[str] = "undefined"
    ) -> AsyncResult:
        _query: Union[str | Query] = query
        if self.is_transaction:
            execution_method = await self.transaction(name=name)
        else:
            _query = Query(
                text=query,
                metadata={"name": name, "infrahub_id": f"{trace.get_current_span().get_span_context().span_id:x}"},
            )
            execution_method = await self.session()

        try:
            response = await execution_method.run(query=_query, parameters=params)
        except ServiceUnavailable as exc:
            log.error("Database Service unavailable", error=str(exc))
            raise DatabaseError(message="Unable to connect to the database") from exc

        return response

    def render_list_comprehension(self, items: str, item_name: str) -> str:
        if self.db_type == DatabaseType.MEMGRAPH:
            return f"extract(i in {items} | i.{item_name})"
        return f"[i IN {items} | i.{item_name}]"

    def render_list_comprehension_with_list(self, items: str, item_names: list[str]) -> str:
        item_names_str = ",".join([f"i.{name}" for name in item_names])
        if self.db_type == DatabaseType.MEMGRAPH:
            return f"extract(i in {items} | [{item_names_str}])"
        return f"[i IN {items} | [{item_names_str}]]"

    def render_uuid_generation(self, node_label: str, node_attr: str, index: int = 1) -> str:
        generate_uuid_query = f"SET {node_label}.{node_attr} = randomUUID()"
        if self.db_type == DatabaseType.MEMGRAPH:
            generate_uuid_query = f"""
            CALL uuid_generator.get() YIELD uuid AS uuid{index}
            SET {node_label}.{node_attr} = uuid{index}
            """
        return generate_uuid_query


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

    trusted_certificates = TrustSystemCAs()
    if config.SETTINGS.database.tls_insecure:
        trusted_certificates = TrustAll()
    elif config.SETTINGS.database.tls_ca_file:
        trusted_certificates = TrustCustomCAs(config.SETTINGS.database.tls_ca_file)

    driver = AsyncGraphDatabase.driver(
        URI,
        auth=(config.SETTINGS.database.username, config.SETTINGS.database.password),
        encrypted=config.SETTINGS.database.tls_enabled,
        trusted_certificates=trusted_certificates,
        notifications_disabled_categories=[NotificationDisabledCategory.UNRECOGNIZED],
        notifications_min_severity=NotificationMinimumSeverity.OFF,
    )

    if config.SETTINGS.database.database_name not in validated_database:
        await validate_database(
            driver=driver, database_name=config.SETTINGS.database.database_name, retry=retry, create_db=True
        )

    return driver


def retry_db_transaction(name: str):
    def func_wrapper(func):
        async def wrapper(*args, **kwargs):
            for attempt in range(1, config.SETTINGS.database.retry_limit + 1):
                try:
                    return await func(*args, **kwargs)
                except TransientError as exc:
                    retry_time: float = random.randrange(100, 500) / 1000
                    log.info(
                        f"Retrying database transaction, attempt {attempt}/{config.SETTINGS.database.retry_limit}",
                        retry_time=retry_time,
                    )
                    log.debug("database transaction failed", message=exc.message)
                    TRANSACTION_RETRIES.labels(name).inc()
                    await asyncio.sleep(retry_time)
                    if attempt == config.SETTINGS.database.retry_limit:
                        raise

        return wrapper

    return func_wrapper
