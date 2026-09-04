from __future__ import annotations

from contextlib import contextmanager
from enum import StrEnum
from typing import TYPE_CHECKING
from urllib.parse import urlsplit, urlunsplit

from prefect.server.database import provide_database_interface
from prefect.server.database.configurations import AioSqliteConfiguration, AsyncPostgresConfiguration
from prefect.server.database.dependencies import (
    temporary_database_config,
    temporary_orm_config,
    temporary_query_components,
)
from prefect.server.database.orm_models import AioSqliteORMConfiguration, AsyncPostgresORMConfiguration
from prefect.server.database.query_components import AioSqliteQueryComponents, AsyncPostgresQueryComponents
from prefect.server.utilities.database import get_dialect
from prefect.settings import PREFECT_API_DATABASE_CONNECTION_URL, get_current_settings, temporary_settings
from sqlalchemy.exc import ArgumentError

if TYPE_CHECKING:
    from collections.abc import Iterator

    from prefect.server.database.configurations import BaseDatabaseConfiguration
    from prefect.server.database.interface import PrefectDBInterface
    from prefect.server.database.orm_models import BaseORMConfiguration
    from prefect.server.database.query_components import BaseQueryComponents

    from infrahub.config import DatabaseSettings

GRAPH_DATABASE_CONNECTION_FIELDS = frozenset(
    {"db_type", "protocol", "username", "password", "address", "port", "database"}
)
"""The ``DatabaseSettings`` fields that identify which graph database a process talks to."""


class TaskManagerDatabaseDialect(StrEnum):
    """Database engines Prefect can back the task manager with."""

    POSTGRESQL = "postgresql"
    SQLITE = "sqlite"


def is_graph_database_configured(database_settings: DatabaseSettings) -> bool:
    """Tell whether the graph database connection was configured explicitly.

    Every connection field has a default, so a process started without any ``INFRAHUB_DB_*``
    setting or ``[database]`` section would happily aim at ``localhost``. Only a connection field
    that was actually provided counts as configuration; tuning fields such as the query size limit
    do not.

    Args:
        database_settings: The loaded graph database settings.

    Returns:
        True when at least one connection field was provided.

    """
    return bool(database_settings.model_fields_set & GRAPH_DATABASE_CONNECTION_FIELDS)


def get_configured_task_manager_database_url() -> str | None:
    """Return the task manager database URL when Prefect was configured with one.

    Prefect falls back to a SQLite file under ``PREFECT_HOME`` when no URL is configured and
    materializes that fallback into its settings, so the settings value alone cannot tell a
    configured database from the fallback; only an explicitly provided ``connection_url`` counts.

    Returns:
        The configured URL, or None when the environment carries no task manager database.

    """
    database_settings = get_current_settings().server.database
    if "connection_url" not in database_settings.model_fields_set or database_settings.connection_url is None:
        return None
    return database_settings.connection_url.get_secret_value()


def get_task_manager_database_dialect(connection_url: str) -> TaskManagerDatabaseDialect:
    """Identify the database engine behind a task manager connection URL.

    Args:
        connection_url: SQLAlchemy URL of the task manager database.

    Returns:
        The dialect the URL points at.

    Raises:
        ValueError: When the URL cannot be parsed or names an engine Prefect does not support.

    """
    try:
        dialect_name = get_dialect(connection_url).name
    except ArgumentError as exc:
        raise ValueError(f"Invalid task manager database URL: {exc}") from exc
    try:
        return TaskManagerDatabaseDialect(dialect_name)
    except ValueError:
        raise ValueError(
            f"Unsupported task manager database {dialect_name!r}: only PostgreSQL and SQLite are supported."
        ) from None


@contextmanager
def task_manager_database(connection_url: str) -> Iterator[PrefectDBInterface]:
    """Provide the Prefect database interface bound to ``connection_url``.

    Prefect caches the first database configuration it builds for the lifetime of the process and
    reuses it for every later ``provide_database_interface`` call, whatever the current settings
    say. The dialect-specific components are therefore built here from ``connection_url`` and
    installed explicitly for the duration of the block, and the URL is installed as a temporary
    setting alongside them so that everything resolving the database from settings agrees. Keep
    the block open while the interface is used: the Alembic upgrade behind ``create_db`` runs in a
    worker thread that resolves the database on its own.

    Args:
        connection_url: SQLAlchemy URL of the task manager database.

    Yields:
        The Prefect database interface for that URL.

    Raises:
        ValueError: When the URL cannot be parsed or names an engine Prefect does not support.

    """
    dialect = get_task_manager_database_dialect(connection_url=connection_url)
    database_config: BaseDatabaseConfiguration
    query_components: BaseQueryComponents
    orm: BaseORMConfiguration
    if dialect is TaskManagerDatabaseDialect.POSTGRESQL:
        database_config = AsyncPostgresConfiguration(connection_url=connection_url)
        query_components = AsyncPostgresQueryComponents()
        orm = AsyncPostgresORMConfiguration()
    else:
        database_config = AioSqliteConfiguration(connection_url=connection_url)
        query_components = AioSqliteQueryComponents()
        orm = AioSqliteORMConfiguration()

    with (
        temporary_settings(updates={PREFECT_API_DATABASE_CONNECTION_URL: connection_url}),
        temporary_database_config(tmp_database_config=database_config),
        temporary_query_components(tmp_queries=query_components),
        temporary_orm_config(tmp_orm_config=orm),
    ):
        yield provide_database_interface()


async def reset_task_manager_database(task_db: PrefectDBInterface) -> None:
    """Drop every table of the task manager database and recreate the schema empty.

    Same procedure as ``prefect server database reset``: the tables are reflected and dropped
    directly instead of being downgraded migration by migration, then the Alembic migrations are
    replayed from scratch.

    Args:
        task_db: Prefect database interface, as provided by ``task_manager_database``.

    """
    await task_db.drop_db()
    await task_db.create_db()
    engine = await task_db.engine()
    await engine.dispose()


def mask_connection_url_password(connection_url: str) -> str:
    """Return ``connection_url`` with the password of its userinfo replaced by ``***``.

    Args:
        connection_url: SQLAlchemy URL, possibly carrying ``user:password@`` credentials.

    Returns:
        The URL unchanged when it carries no password, masked otherwise.

    """
    parts = urlsplit(connection_url)
    userinfo, separator, hostport = parts.netloc.rpartition("@")
    if not separator or ":" not in userinfo:
        return connection_url
    username = userinfo.partition(":")[0]
    return urlunsplit(parts._replace(netloc=f"{username}:***@{hostport}"))
