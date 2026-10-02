import pytest
from prefect.server.database.configurations import AioSqliteConfiguration, AsyncPostgresConfiguration
from prefect.settings import PREFECT_API_DATABASE_CONNECTION_URL, temporary_settings

from infrahub.cli.db_commands.reset import (
    GRAPH_DATABASE_CONNECTION_FIELDS,
    TaskManagerDatabaseDialect,
    get_configured_task_manager_database_url,
    get_task_manager_database_dialect,
    is_graph_database_configured,
    mask_connection_url_password,
    task_manager_database,
)
from infrahub.config import DatabaseSettings


@pytest.mark.parametrize(
    ("connection_url", "expected"),
    [
        pytest.param(
            "postgresql+asyncpg://postgres:s3cret@task-manager-db:5432/prefect",
            "postgresql+asyncpg://postgres:***@task-manager-db:5432/prefect",
            id="password",
        ),
        pytest.param(
            "postgresql+asyncpg://user:p%40ss%3Aword@[::1]:5432/prefect?ssl=require",
            "postgresql+asyncpg://user:***@[::1]:5432/prefect?ssl=require",
            id="encoded-password-ipv6-host-query",
        ),
        pytest.param(
            "postgresql+asyncpg://postgres@task-manager-db:5432/prefect",
            "postgresql+asyncpg://postgres@task-manager-db:5432/prefect",
            id="username-only",
        ),
        pytest.param(
            "postgresql+asyncpg://task-manager-db:5432/prefect",
            "postgresql+asyncpg://task-manager-db:5432/prefect",
            id="no-credentials",
        ),
        pytest.param(
            "sqlite+aiosqlite:////tmp/prefect.db",
            "sqlite+aiosqlite:////tmp/prefect.db",
            id="sqlite-file",
        ),
    ],
)
def test_mask_connection_url_password(connection_url: str, expected: str) -> None:
    assert mask_connection_url_password(connection_url=connection_url) == expected


@pytest.mark.parametrize(
    ("connection_url", "expected"),
    [
        pytest.param(
            "postgresql+asyncpg://postgres:postgres@task-manager-db:5432/prefect",
            TaskManagerDatabaseDialect.POSTGRESQL,
            id="postgresql",
        ),
        pytest.param("sqlite+aiosqlite:////tmp/prefect.db", TaskManagerDatabaseDialect.SQLITE, id="sqlite"),
    ],
)
def test_get_task_manager_database_dialect(connection_url: str, expected: TaskManagerDatabaseDialect) -> None:
    assert get_task_manager_database_dialect(connection_url=connection_url) is expected


@pytest.mark.parametrize(
    ("connection_url", "message"),
    [
        pytest.param("task-manager-db:5432/prefect", "Invalid task manager database URL", id="not-a-url"),
        pytest.param("mysql+pymysql://user:password@db/prefect", "Unsupported task manager database", id="mysql"),
    ],
)
def test_get_task_manager_database_dialect_rejects(connection_url: str, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        get_task_manager_database_dialect(connection_url=connection_url)


class TestIsGraphDatabaseConfigured:
    def test_nothing_provided(self) -> None:
        assert not is_graph_database_configured(database_settings=DatabaseSettings.model_construct(_fields_set=set()))

    @pytest.mark.parametrize("field", sorted(GRAPH_DATABASE_CONNECTION_FIELDS))
    def test_connection_field_provided(self, field: str) -> None:
        settings = DatabaseSettings.model_construct(_fields_set={field})
        assert is_graph_database_configured(database_settings=settings)

    def test_tuning_field_only(self) -> None:
        settings = DatabaseSettings.model_construct(_fields_set={"query_size_limit", "retry_limit"})
        assert not is_graph_database_configured(database_settings=settings)


class TestGetConfiguredTaskManagerDatabaseUrl:
    def test_unset_ignores_the_sqlite_fallback(self) -> None:
        with temporary_settings(updates={PREFECT_API_DATABASE_CONNECTION_URL: None}):
            assert get_configured_task_manager_database_url() is None

    def test_configured(self) -> None:
        connection_url = "postgresql+asyncpg://postgres:postgres@task-manager-db:5432/prefect"
        with temporary_settings(updates={PREFECT_API_DATABASE_CONNECTION_URL: connection_url}):
            assert get_configured_task_manager_database_url() == connection_url


class TestTaskManagerDatabase:
    def test_binds_each_interface_to_its_own_url(self) -> None:
        """Prefect pins the first database configuration per process; every later URL must still win."""
        sqlite_url = "sqlite+aiosqlite:////tmp/first.db"
        postgres_url = "postgresql+asyncpg://postgres:postgres@task-manager-db:5432/prefect"

        with task_manager_database(connection_url=sqlite_url) as sqlite_db:
            assert isinstance(sqlite_db.database_config, AioSqliteConfiguration)
            assert sqlite_db.database_config.connection_url == sqlite_url

        with task_manager_database(connection_url=postgres_url) as postgres_db:
            assert isinstance(postgres_db.database_config, AsyncPostgresConfiguration)
            assert postgres_db.database_config.connection_url == postgres_url
