from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, ClassVar

import pytest
from neo4j import AsyncGraphDatabase
from neo4j.exceptions import ClientError, TransientError
from typing_extensions import Self

import infrahub.core.migrations  # noqa: F401  imports every schema migration module, so every query class is defined
from infrahub import config
from infrahub.core.constants import SchemaPathType
from infrahub.core.migrations.query import AttributeMigrationQuery, MigrationQuery
from infrahub.core.migrations.query.selection import MigrationSelectionQuery
from infrahub.core.migrations.schema.node_relationship_remove import RelationshipMigrationQuery
from infrahub.core.migrations.shared import GraphMigration, MigrationInput, SchemaMigration
from infrahub.core.path import SchemaPath
from infrahub.core.query import Query, QueryType
from infrahub.database import InfrahubDatabase

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Generator, Sequence

    from infrahub.core.branch import Branch
    from infrahub.core.migrations.query import MigrationBaseQuery


@pytest.fixture
def _fast_retry() -> Generator[None, None, None]:
    original_retry_limit = config.SETTINGS.database.retry_limit
    original_base_delay = config.SETTINGS.database.retry_base_delay
    original_max_delay = config.SETTINGS.database.retry_max_delay
    original_jitter_max = config.SETTINGS.database.retry_jitter_max

    config.SETTINGS.database.retry_limit = 3
    config.SETTINGS.database.retry_base_delay = 0.01
    config.SETTINGS.database.retry_max_delay = 0.1
    config.SETTINGS.database.retry_jitter_max = 0.0
    yield
    config.SETTINGS.database.retry_limit = original_retry_limit
    config.SETTINGS.database.retry_base_delay = original_base_delay
    config.SETTINGS.database.retry_max_delay = original_max_delay
    config.SETTINGS.database.retry_jitter_max = original_jitter_max


class DeadlockOnceMigrationQuery(MigrationQuery, MigrationSelectionQuery):
    name = "test_deadlock_once_migration"
    type: QueryType = QueryType.WRITE
    insert_return = False

    calls: ClassVar[int] = 0

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:
        self.add_to_query("RETURN 1 AS num")

    async def execute(self, db: InfrahubDatabase, timeout_seconds: float | None = None) -> Self:
        type(self).calls += 1
        if type(self).calls == 1:
            raise TransientError("deadlock detected")
        return await super().execute(db=db, timeout_seconds=timeout_seconds)

    def get_nbr_migrations_executed(self) -> int:
        return 1


class AlwaysDeadlockMigrationQuery(MigrationQuery, MigrationSelectionQuery):
    name = "test_always_deadlock_migration"
    type: QueryType = QueryType.WRITE
    insert_return = False

    calls: ClassVar[int] = 0

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:
        self.add_to_query("RETURN 1 AS num")

    async def execute(self, db: InfrahubDatabase, timeout_seconds: float | None = None) -> Self:
        type(self).calls += 1
        raise TransientError("deadlock detected")


def _entity_not_found_error() -> ClientError:
    error = ClientError("entity not found")
    error._neo4j_code = "Neo.ClientError.Statement.EntityNotFound"
    return error


class EntityNotFoundOnceMigrationQuery(MigrationQuery, MigrationSelectionQuery):
    name = "test_entity_not_found_once_migration"
    type: QueryType = QueryType.WRITE
    insert_return = False

    calls: ClassVar[int] = 0

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:
        self.add_to_query("RETURN 1 AS num")

    async def execute(self, db: InfrahubDatabase, timeout_seconds: float | None = None) -> Self:
        type(self).calls += 1
        if type(self).calls == 1:
            raise _entity_not_found_error()
        return await super().execute(db=db, timeout_seconds=timeout_seconds)

    def get_nbr_migrations_executed(self) -> int:
        return 1


class DeadlockOnceGraphQuery(Query):
    name = "test_deadlock_once_graph"
    type: QueryType = QueryType.WRITE
    insert_return = False

    calls: ClassVar[int] = 0

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:
        self.add_to_query("RETURN 1 AS num")

    async def execute(self, db: InfrahubDatabase, timeout_seconds: float | None = None) -> Self:
        type(self).calls += 1
        if type(self).calls == 1:
            raise TransientError("deadlock detected")
        return await super().execute(db=db, timeout_seconds=timeout_seconds)


class AlwaysDeadlockGraphQuery(Query):
    name = "test_always_deadlock_graph"
    type: QueryType = QueryType.WRITE
    insert_return = False

    calls: ClassVar[int] = 0

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:
        self.add_to_query("RETURN 1 AS num")

    async def execute(self, db: InfrahubDatabase, timeout_seconds: float | None = None) -> Self:
        type(self).calls += 1
        raise TransientError("deadlock detected")


def _make_schema_migration(queries: Sequence[type[MigrationBaseQuery]]) -> SchemaMigration:
    return SchemaMigration(
        name="test.migration",
        queries=queries,
        schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestKind", field_name="name"),
    )


@pytest.mark.usefixtures("_fast_retry")
class TestMigrationTransientErrorRetry:
    @pytest.fixture(autouse=True)
    def _reset_query_call_counts(self) -> None:
        DeadlockOnceMigrationQuery.calls = 0
        AlwaysDeadlockMigrationQuery.calls = 0
        EntityNotFoundOnceMigrationQuery.calls = 0
        DeadlockOnceGraphQuery.calls = 0
        AlwaysDeadlockGraphQuery.calls = 0

    async def test_schema_migration_retries_transient_error(self, db: InfrahubDatabase, default_branch: Branch) -> None:
        migration = _make_schema_migration(queries=[DeadlockOnceMigrationQuery])

        result = await migration.execute(migration_input=MigrationInput(db=db), branch=default_branch)

        assert result.errors == []
        assert result.success
        assert result.nbr_migrations_executed == 1
        assert DeadlockOnceMigrationQuery.calls == 2

    async def test_schema_migration_retries_entity_not_found(
        self, db: InfrahubDatabase, default_branch: Branch
    ) -> None:
        migration = _make_schema_migration(queries=[EntityNotFoundOnceMigrationQuery])

        result = await migration.execute(migration_input=MigrationInput(db=db), branch=default_branch)

        assert result.errors == []
        assert result.success
        assert result.nbr_migrations_executed == 1
        assert EntityNotFoundOnceMigrationQuery.calls == 2

    async def test_schema_migration_raises_after_retries_exhausted(
        self, db: InfrahubDatabase, default_branch: Branch
    ) -> None:
        migration = _make_schema_migration(queries=[AlwaysDeadlockMigrationQuery])

        with pytest.raises(TransientError, match=r"deadlock detected"):
            await migration.execute(migration_input=MigrationInput(db=db), branch=default_branch)

        assert AlwaysDeadlockMigrationQuery.calls == config.SETTINGS.database.retry_limit

    async def test_graph_migration_retries_transient_error(self, db: InfrahubDatabase) -> None:
        migration = GraphMigration(
            name="test-graph-migration",
            description="Test graph migration retry",
            minimum_version=0,
            queries=[DeadlockOnceGraphQuery],
        )

        result = await migration.execute(migration_input=MigrationInput(db=db))

        assert result.errors == []
        assert result.success
        assert DeadlockOnceGraphQuery.calls == 2

    async def test_graph_migration_outside_transaction_records_transient_error(self, db: InfrahubDatabase) -> None:
        migration = GraphMigration(
            name="test-graph-migration",
            description="Test graph migration outside a transaction",
            minimum_version=0,
            queries=[AlwaysDeadlockGraphQuery],
        )

        result = await migration.do_execute(migration_input=MigrationInput(db=db))

        assert not result.success
        assert result.errors == ["deadlock detected"]
        assert AlwaysDeadlockGraphQuery.calls == 1


class _MigrationWithoutNodeScope(SchemaMigration):
    applies_node_scope = False


@dataclass
class ScopedInputTestCase:
    name: str
    migration_class: type[SchemaMigration]
    node_ids: frozenset[str] | None
    expected_node_ids: frozenset[str] | None


SCOPED_INPUT_TEST_CASES: list[ScopedInputTestCase] = [
    ScopedInputTestCase(
        name="applies_scope_keeps_node_ids",
        migration_class=SchemaMigration,
        node_ids=frozenset({"node-a", "node-b"}),
        expected_node_ids=frozenset({"node-a", "node-b"}),
    ),
    ScopedInputTestCase(
        name="applies_scope_keeps_empty_set",
        migration_class=SchemaMigration,
        node_ids=frozenset(),
        expected_node_ids=frozenset(),
    ),
    ScopedInputTestCase(
        name="applies_scope_keeps_no_scope",
        migration_class=SchemaMigration,
        node_ids=None,
        expected_node_ids=None,
    ),
    ScopedInputTestCase(
        name="ignores_scope_drops_node_ids",
        migration_class=_MigrationWithoutNodeScope,
        node_ids=frozenset({"node-a", "node-b"}),
        expected_node_ids=None,
    ),
    ScopedInputTestCase(
        name="ignores_scope_drops_empty_set",
        migration_class=_MigrationWithoutNodeScope,
        node_ids=frozenset(),
        expected_node_ids=None,
    ),
]


@pytest.fixture
async def unconnected_db() -> AsyncGenerator[InfrahubDatabase, None]:
    # Building a driver opens no connection, and the migration only carries the database in its input.
    driver = AsyncGraphDatabase.driver("bolt://127.0.0.1:9", auth=("neo4j", "unused"))
    yield InfrahubDatabase(driver=driver)
    await driver.close()


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in SCOPED_INPUT_TEST_CASES])
def test_scoped_input(unconnected_db: InfrahubDatabase, test_case: ScopedInputTestCase) -> None:
    migration = test_case.migration_class(
        name="test.migration",
        queries=[],
        schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestKind", field_name="name"),
    )
    migration_input = MigrationInput(db=unconnected_db, user_id="test-user", node_ids=test_case.node_ids)

    scoped = migration.scoped_input(migration_input=migration_input)

    assert scoped.node_ids == test_case.expected_node_ids
    assert scoped.db is unconnected_db
    assert scoped.at == migration_input.at
    assert scoped.user_id == "test-user"


def _all_subclasses(cls: type) -> set[type]:
    subclasses: set[type] = set()
    for subclass in cls.__subclasses__():
        subclasses.add(subclass)
        subclasses |= _all_subclasses(subclass)
    return subclasses


def test_every_migration_bound_query_is_a_selection_query() -> None:
    query_classes = (
        _all_subclasses(MigrationQuery)
        | _all_subclasses(AttributeMigrationQuery)
        | _all_subclasses(RelationshipMigrationQuery)
    )

    assert sorted(cls.__name__ for cls in query_classes if cls.__module__.startswith("infrahub.")) == [
        "AttributeKindUpdateMigrationQuery",
        "AttributeNameUpdateMigrationQuery01",
        "NodeAttributeAddMigrationQuery01",
        "NodeAttributeRemoveMigrationQuery01",
        "NodeKindUpdateMigrationQuery01",
        "NodeRelationshipRemoveMigrationQuery",
        "NodeRemoveMigrationBaseQuery",
        "NodeRemoveMigrationQueryIn",
        "NodeRemoveMigrationQueryOut",
        "ProfilesAttributeAddMigrationQuery",
        "ProfilesAttributeRemoveMigrationQuery",
        "TemplatesAttributeAddMigrationQuery",
        "TemplatesAttributeRemoveMigrationQuery",
    ]
    assert {cls for cls in query_classes if not issubclass(cls, MigrationSelectionQuery)} == set()
