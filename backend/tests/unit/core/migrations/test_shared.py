from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, ClassVar

import pytest
from neo4j.exceptions import ClientError, TransientError
from typing_extensions import Self

from infrahub import config
from infrahub.core.constants import SchemaPathType
from infrahub.core.migrations.query import MigrationQuery
from infrahub.core.migrations.shared import GraphMigration, MigrationInput, SchemaMigration
from infrahub.core.path import SchemaPath
from infrahub.core.query import Query, QueryType
from tests.unit.core.migrations.schema.helpers import (
    CAR_KINDS,
    INTERFACE_KINDS,
    full_schema_branch,
    interface_used_by,
    schema_branch,
)

if TYPE_CHECKING:
    from collections.abc import Generator, Sequence

    from infrahub.core.branch import Branch
    from infrahub.core.migrations.query import MigrationBaseQuery
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase


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


class DeadlockOnceMigrationQuery(MigrationQuery):
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


class AlwaysDeadlockMigrationQuery(MigrationQuery):
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


class EntityNotFoundOnceMigrationQuery(MigrationQuery):
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


@dataclass(frozen=True, kw_only=True)
class ChangedKindsCase:
    name: str
    schema_path: SchemaPath
    previous_schema: SchemaBranch
    new_schema: SchemaBranch
    expected: frozenset[str]


CHANGED_KINDS_CASES: list[ChangedKindsCase] = [
    ChangedKindsCase(
        name="node_attribute",
        schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestingCar", field_name="color"),
        previous_schema=full_schema_branch(),
        new_schema=full_schema_branch(),
        expected=CAR_KINDS,
    ),
    ChangedKindsCase(
        name="generic_attribute",
        schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestingInterface", field_name="serial"),
        previous_schema=full_schema_branch(),
        new_schema=full_schema_branch(),
        expected=INTERFACE_KINDS,
    ),
    ChangedKindsCase(
        name="generic_used_by_from_both_schemas",
        schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestingInterface", field_name="serial"),
        previous_schema=schema_branch(interface_used_by(used_by=["TestingPhysicalInterface"])),
        new_schema=schema_branch(interface_used_by(used_by=["TestingVirtualInterface"])),
        expected=INTERFACE_KINDS,
    ),
]


@pytest.mark.parametrize("case", [pytest.param(case, id=case.name) for case in CHANGED_KINDS_CASES])
def test_changed_kinds_are_the_dependent_kinds_in_both_schemas(case: ChangedKindsCase) -> None:
    changed_kinds = SchemaMigration.get_changed_kinds(
        schema_path=case.schema_path, previous_schema=case.previous_schema, new_schema=case.new_schema
    )

    assert changed_kinds == case.expected
