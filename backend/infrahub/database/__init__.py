from __future__ import annotations

import asyncio
import random
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable, Coroutine, TypeVar

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
from infrahub.constants.database import DatabaseType, Neo4jRuntime
from infrahub.core import registry
from infrahub.core.constants import (
    GLOBAL_BRANCH_NAME,
)
from infrahub.core.query import QueryType
from infrahub.exceptions import DatabaseError
from infrahub.log import get_logger
from infrahub.utils import InfrahubStringEnum

from .metrics import CONNECTION_POOL_USAGE, QUERY_EXECUTION_METRICS, TRANSACTION_RETRIES

if TYPE_CHECKING:
    from types import TracebackType

    from infrahub.core.branch import Branch
    from infrahub.core.schema import GenericSchema, MainSchemaTypes, NodeSchema
    from infrahub.core.schema.schema_branch import SchemaBranch

validated_database = {}
R = TypeVar("R")

log = get_logger()


@dataclass
class QueryConfig:
    neo4j_runtime: Neo4jRuntime = Neo4jRuntime.DEFAULT
    profile_memory: bool = False


class InfrahubDatabaseMode(InfrahubStringEnum):
    DRIVER = "driver"
    SESSION = "session"
    TRANSACTION = "transaction"


class InfrahubDatabaseSessionMode(InfrahubStringEnum):
    READ = "read"
    WRITE = "write"


DRIVER_REFRESH_INTERVAL_SECONDS = 60.0


class DriverState:
    """Track references and lifecycle management for an asynchronous driver."""

    def __init__(self, driver: AsyncDriver, refresh_interval: float = DRIVER_REFRESH_INTERVAL_SECONDS) -> None:
        self.driver: AsyncDriver = driver
        self.refresh_interval = refresh_interval
        self._usage_count: int = 0
        self._usage_lock = asyncio.Lock()
        self._refresh_lock = asyncio.Lock()
        self._closed: bool = False
        self._last_refresh: float = time.monotonic()

    async def acquire(self) -> AsyncDriver:
        """Mark the driver as in-use and return it."""

        if self._closed:
            raise RuntimeError("Cannot acquire a closed driver state.")

        async with self._usage_lock:
            if self._closed:
                raise RuntimeError("Cannot acquire a closed driver state.")
            self._usage_count += 1
            return self.driver

    async def release(self) -> None:
        """Decrease the usage counter and refresh the driver if needed."""

        if self._closed:
            return

        async with self._usage_lock:
            if self._usage_count == 0:
                log.warning("Attempted to release a driver with zero usage count.")
                return
            self._usage_count -= 1
            usage_remaining = self._usage_count

        if usage_remaining == 0:
            await self._maybe_refresh()

    async def close(self) -> None:
        """Close the underlying driver and prevent further refreshes."""

        if self._closed:
            return

        self._closed = True
        async with self._refresh_lock:
            async with self._usage_lock:
                current_driver = self.driver
                self._usage_count = 0
        await current_driver.close()

    async def _maybe_refresh(self) -> None:
        if self._closed:
            return

        if time.monotonic() - self._last_refresh < self.refresh_interval:
            return

        old_driver: AsyncDriver | None = None
        async with self._refresh_lock:
            if self._closed:
                return

            async with self._usage_lock:
                refresh_due = (
                    not self._closed
                    and self._usage_count == 0
                    and time.monotonic() - self._last_refresh >= self.refresh_interval
                )

            if not refresh_due:
                return

            try:
                new_driver = await _create_driver()
            except Exception as exc:
                log.exception("Failed to refresh Neo4j driver", error=str(exc))
                return

            async with self._usage_lock:
                if self._usage_count != 0 or self._closed:
                    await new_driver.close()
                    return
                old_driver = self.driver
                self.driver = new_driver
                self._last_refresh = time.monotonic()

        if old_driver:
            await old_driver.close()
            log.info("Neo4j driver refreshed")


def get_branch_name(branch: Branch | str | None = None) -> str:
    if not branch:
        return registry.default_branch
    if isinstance(branch, str):
        return branch

    return branch.name


class DatabaseSchemaManager:
    def __init__(self, db: InfrahubDatabase) -> None:
        self._db = db

    def get(self, name: str, branch: Branch | str | None = None, duplicate: bool = True) -> MainSchemaTypes:
        branch_name = get_branch_name(branch=branch)
        if branch_name not in self._db._schemas:
            return registry.schema.get(name=name, branch=branch, duplicate=duplicate)
        return self._db._schemas[branch_name].get(name=name, duplicate=duplicate)

    def get_node_schema(self, name: str, branch: Branch | str | None = None, duplicate: bool = True) -> NodeSchema:
        schema = self.get(name=name, branch=branch, duplicate=duplicate)
        if schema.is_node_schema:
            return schema

        raise ValueError("The selected node is not of type NodeSchema")

    def get_generic_schema(
        self, name: str, branch: Branch | str | None = None, duplicate: bool = True
    ) -> GenericSchema:
        schema = self.get(name=name, branch=branch, duplicate=duplicate)
        if schema.is_generic_schema:
            return schema

        raise ValueError("The selected node is not of type GenericSchema")

    def set(self, name: str, schema: MainSchemaTypes, branch: str | None = None) -> int:
        branch_name = get_branch_name(branch=branch)
        if branch_name not in self._db._schemas:
            return registry.schema.set(name=name, schema=schema, branch=branch)
        return self._db._schemas[branch_name].set(name=name, schema=schema)

    def has(self, name: str, branch: Branch | str | None = None) -> bool:
        branch_name = get_branch_name(branch=branch)
        if branch_name not in self._db._schemas:
            return registry.schema.has(name=name, branch=branch)
        return self._db._schemas[branch_name].has(name=name)

    def get_full(self, branch: Branch | str | None = None, duplicate: bool = True) -> dict[str, MainSchemaTypes]:
        branch_name = get_branch_name(branch=branch)
        if branch_name not in self._db._schemas:
            return registry.schema.get_full(branch=branch)
        return self._db._schemas[branch_name].get_all(duplicate=duplicate)

    async def get_full_safe(
        self, branch: Branch | str | None = None, duplicate: bool = True
    ) -> dict[str, MainSchemaTypes]:
        await lock.registry.local_schema_wait()
        return self.get_full(branch=branch, duplicate=duplicate)

    def get_schema_branch(self, name: str) -> SchemaBranch:
        """Return a schema branch object based on its name.

        If the branch is the global one, the default branch will be returned.
        """
        branch_name = registry.default_branch if name == GLOBAL_BRANCH_NAME else name
        if branch_name not in self._db._schemas:
            return registry.schema.get_schema_branch(name=branch_name)
        return self._db._schemas[branch_name]


class InfrahubDatabase:
    """Base class for database access"""

    def __init__(
        self,
        driver: AsyncDriver | None = None,
        mode: InfrahubDatabaseMode = InfrahubDatabaseMode.DRIVER,
        db_type: DatabaseType | None = None,
        default_neo4j_runtime: Neo4jRuntime = Neo4jRuntime.DEFAULT,
        schemas: list[SchemaBranch] | None = None,
        session: AsyncSession | None = None,
        session_mode: InfrahubDatabaseSessionMode = InfrahubDatabaseSessionMode.WRITE,
        transaction: AsyncTransaction | None = None,
        queries_names_to_config: dict[str, QueryConfig] | None = None,
        driver_state: DriverState | None = None,
    ):
        if driver_state is None:
            if driver is None:
                raise ValueError("A driver instance is required when driver_state is not provided.")
            self._driver_state: DriverState = DriverState(driver=driver)
        else:
            self._driver_state = driver_state
            if driver is not None and driver_state.driver is not driver:
                self._driver_state.driver = driver

        self._mode: InfrahubDatabaseMode = mode
        self._session: AsyncSession | None = session
        self._session_mode: InfrahubDatabaseSessionMode = session_mode
        self._is_session_local: bool = False
        self._transaction: AsyncTransaction | None = transaction
        self.default_neo4j_runtime = default_neo4j_runtime
        self.queries_names_to_config = queries_names_to_config if queries_names_to_config is not None else {}

        if schemas:
            self._schemas: dict[str, SchemaBranch] = {schema.name: schema for schema in schemas}
        else:
            self._schemas = {}
        self.schema: DatabaseSchemaManager = DatabaseSchemaManager(db=self)

        if db_type and isinstance(db_type, DatabaseType):
            self.db_type = db_type
        else:
            self.db_type = config.SETTINGS.database.db_type

    @property
    def driver(self) -> AsyncDriver:
        return self._driver_state.driver

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

    def get_context(self) -> dict[str, Any]:
        """
        This method is meant to be overridden by subclasses in order to fill in subclass attributes
        to methods returning a copy of this object using self.__class__ constructor.
        """

        return {}

    def add_schema(self, schema: SchemaBranch, name: str | None = None) -> None:
        self._schemas[name or schema.name] = schema

    def purge_inactive_schemas(self, active_branches: list[str]) -> list[str]:
        """Return non active schema branches that were purged."""
        removed_branches: list[str] = []
        for branch_name in list(self._schemas.keys()):
            if branch_name not in active_branches:
                del self._schemas[branch_name]
                removed_branches.append(branch_name)

        return removed_branches

    def start_session(self, read_only: bool = False, schemas: list[SchemaBranch] | None = None) -> InfrahubDatabase:
        """Create a new InfrahubDatabase object in Session mode."""
        session_mode = InfrahubDatabaseSessionMode.WRITE
        if read_only:
            session_mode = InfrahubDatabaseSessionMode.READ

        context = self.get_context()
        schemas_to_use = list(schemas) if schemas is not None else list(self._schemas.values())

        return self.__class__(
            mode=InfrahubDatabaseMode.SESSION,
            db_type=self.db_type,
            default_neo4j_runtime=self.default_neo4j_runtime,
            schemas=schemas_to_use,
            driver_state=self._driver_state,
            session_mode=session_mode,
            queries_names_to_config=self.queries_names_to_config,
            **context,
        )

    def start_transaction(self, schemas: list[SchemaBranch] | None = None) -> InfrahubDatabase:
        context = self.get_context()
        schemas_to_use = list(schemas) if schemas is not None else list(self._schemas.values())

        return self.__class__(
            mode=InfrahubDatabaseMode.TRANSACTION,
            db_type=self.db_type,
            default_neo4j_runtime=self.default_neo4j_runtime,
            schemas=schemas_to_use,
            driver_state=self._driver_state,
            session=self._session,
            session_mode=self._session_mode,
            queries_names_to_config=self.queries_names_to_config,
            **context,
        )

    async def session(self) -> AsyncSession:
        if self._session:
            return self._session

        await self._driver_state.acquire()

        try:
            default_access_mode = (
                READ_ACCESS if self._session_mode == InfrahubDatabaseSessionMode.READ else WRITE_ACCESS
            )
            self._session = self.driver.session(
                database=config.SETTINGS.database.database_name, default_access_mode=default_access_mode
            )
        except Exception:
            await self._driver_state.release()
            raise

        self._is_session_local = True
        return self._session

    async def transaction(self, name: str | None) -> AsyncTransaction:
        if self._transaction:
            return self._transaction

        session = await self.session()
        self._transaction = await session.begin_transaction(
            metadata={"name": name, "infrahub_id": f"{trace.get_current_span().get_span_context().span_id:x}"}
        )
        return self._transaction

    async def __aenter__(self) -> Self:
        if self._mode == InfrahubDatabaseMode.SESSION:
            await self.session()
        elif self._mode == InfrahubDatabaseMode.TRANSACTION:
            session = await self.session()
            self._transaction = await session.begin_transaction()

        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if self._mode == InfrahubDatabaseMode.SESSION:
            if self._session and self._is_session_local:
                await self._session.close()
                self._session = None
                self._is_session_local = False
                await self._driver_state.release()
            return

        if self._mode == InfrahubDatabaseMode.TRANSACTION:
            if self._transaction is not None:
                if exc_type is not None:
                    await self._transaction.rollback()
                else:
                    try:
                        await self._transaction.commit()
                    except Neo4jError as exc:
                        raise exc
                    finally:
                        await self._transaction.close()
                self._transaction = None

            if self._is_session_local:
                if self._session:
                    await self._session.close()
                    self._session = None
                self._is_session_local = False
                await self._driver_state.release()

    async def close(self) -> None:
        if self._session and self._is_session_local:
            await self._session.close()
            self._session = None
            self._is_session_local = False
            await self._driver_state.release()

        await self._driver_state.close()

    async def execute_query(
        self,
        query: str,
        params: dict[str, Any] | None = None,
        name: str = "undefined",
        context: dict[str, str] | None = None,
        type: QueryType | None = None,
    ) -> list[Record]:
        results, _ = await self.execute_query_with_metadata(
            query=query, params=params, name=name, context=context, type=type
        )
        return results

    async def execute_query_with_metadata(
        self,
        query: str,
        params: dict[str, Any] | None = None,
        name: str = "undefined",
        context: dict[str, str] | None = None,
        type: QueryType | None = None,
    ) -> tuple[list[Record], dict[str, Any]]:
        driver = self.driver
        connpool_usage = driver._pool.in_use_connection_count(driver._pool.address)
        CONNECTION_POOL_USAGE.labels(driver._pool.address).set(float(connpool_usage))

        if config.SETTINGS.database.max_concurrent_queries:
            while connpool_usage > config.SETTINGS.database.max_concurrent_queries:
                await asyncio.sleep(config.SETTINGS.database.max_concurrent_queries_delay)
                connpool_usage = driver._pool.in_use_connection_count(driver._pool.address)

        with trace.get_tracer(__name__).start_as_current_span("execute_db_query_with_metadata") as span:
            span.set_attribute("query", query)
            if name:
                span.set_attribute("query_name", name)

            runtime = self.default_neo4j_runtime

            if self.db_type == DatabaseType.NEO4J:
                query_config = self.queries_names_to_config.get(name, None)

                if query_config and query_config.neo4j_runtime not in [Neo4jRuntime.DEFAULT, Neo4jRuntime.UNDEFINED]:
                    runtime = query_config.neo4j_runtime

                if (
                    type
                    and type == QueryType.READ
                    and runtime not in [Neo4jRuntime.DEFAULT, Neo4jRuntime.UNDEFINED]
                    and not (self.is_transaction and runtime in [Neo4jRuntime.PARALLEL])
                ):
                    query = f"CYPHER runtime = {runtime.value}\n" + query
                else:
                    runtime = Neo4jRuntime.DEFAULT

                if query_config and query_config.profile_memory:
                    query = "PROFILE\n" + query

            labels = {
                "type": type.value if type else self._session_mode.value,
                "query": name,
                "runtime": runtime.value,
                "context1": "",
                "context2": "",
            }
            if context:
                labels.update(
                    {
                        f"context{idx + 1}": f"{key}__{value}"
                        for idx, (key, value) in enumerate(context.items())
                        if idx <= 1
                    }
                )

            with QUERY_EXECUTION_METRICS.labels(**labels).time():
                response = await self.run_query(query=query, params=params, name=name)
                if response is None:
                    span.set_attribute("rows", "empty")
                    return [], {}
                results = [item async for item in response]
                span.set_attribute("rows", len(results))
                return results, response._metadata or {}

    async def run_query(
        self, query: str, params: dict[str, Any] | None = None, name: str | None = "undefined"
    ) -> AsyncResult:
        _query: str | Query = query
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

    def get_id_function_name(self) -> str:
        if self.db_type == DatabaseType.NEO4J:
            return "elementId"
        return "ID"

    def to_database_id(self, db_id: str | int) -> str | int:
        if self.db_type == DatabaseType.NEO4J:
            return db_id
        try:
            return int(db_id)
        except ValueError:
            return db_id


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


async def _create_driver(retry: int = 0) -> AsyncDriver:
    trusted_certificates = TrustSystemCAs()
    if config.SETTINGS.database.tls_insecure:
        trusted_certificates = TrustAll()
    elif config.SETTINGS.database.tls_ca_file:
        trusted_certificates = TrustCustomCAs(config.SETTINGS.database.tls_ca_file)

    driver = AsyncGraphDatabase.driver(
        config.SETTINGS.database.database_uri,
        auth=(config.SETTINGS.database.username, config.SETTINGS.database.password),
        encrypted=config.SETTINGS.database.tls_enabled,
        trusted_certificates=trusted_certificates,
        notifications_disabled_categories=[
            NotificationDisabledCategory.UNRECOGNIZED,
        ],
        notifications_min_severity=NotificationMinimumSeverity.WARNING,
    )

    if config.SETTINGS.database.database_name not in validated_database:
        await validate_database(
            driver=driver, database_name=config.SETTINGS.database.database_name, retry=retry, create_db=True
        )

    return driver


async def get_db(retry: int = 0) -> AsyncDriver:
    return await _create_driver(retry=retry)


def retry_db_transaction(
    name: str,
) -> Callable[[Callable[..., Coroutine[Any, Any, R]]], Callable[..., Coroutine[Any, Any, R]]]:
    def func_wrapper(func: Callable[..., Coroutine[Any, Any, R]]) -> Callable[..., Coroutine[Any, Any, R]]:
        async def wrapper(*args: Any, **kwargs: Any) -> R:
            error = Exception()
            for attempt in range(1, config.SETTINGS.database.retry_limit + 1):
                try:
                    return await func(*args, **kwargs)
                except (TransientError, ClientError) as exc:
                    if isinstance(exc, ClientError):
                        if exc.code != "Neo.ClientError.Statement.EntityNotFound":
                            raise exc
                    retry_time: float = random.randrange(100, 500) / 1000
                    log.exception("Retry handler caught database error")
                    log.info(
                        f"Retrying database transaction, attempt {attempt}/{config.SETTINGS.database.retry_limit}",
                        retry_time=retry_time,
                    )
                    log.debug("Database transaction failed", message=exc.message)
                    TRANSACTION_RETRIES.labels(name).inc()
                    await asyncio.sleep(retry_time)
                    if attempt == config.SETTINGS.database.retry_limit:
                        error = exc
                        break
            raise error

        return wrapper

    return func_wrapper
