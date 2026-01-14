from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Sequence

from pydantic import BaseModel, ConfigDict, Field
from rich.console import Console
from typing_extensions import Self

from infrahub.core import registry
from infrahub.core.constants import SYSTEM_USER_ID
from infrahub.core.path import SchemaPath  # noqa: TC001
from infrahub.core.query import Query  # noqa: TC001
from infrahub.core.schema import AttributeSchema, MainSchemaTypes, RelationshipSchema, SchemaRoot, internal_schema
from infrahub.core.timestamp import Timestamp

from .query import MigrationBaseQuery  # noqa: TC001

MIGRATION_LOG_TIME_FORMAT = "[%Y-%m-%d %H:%M:%S]"
_migration_console: Console | None = None


def get_migration_console() -> Console:
    global _migration_console

    if _migration_console is None:
        _migration_console = Console(log_time_format=MIGRATION_LOG_TIME_FORMAT)

    return _migration_console


if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase


class MigrationResult(BaseModel):
    errors: list[str] = Field(default_factory=list)
    nbr_migrations_executed: int = 0

    @property
    def success(self) -> bool:
        if not self.errors:
            return True

        return False


@dataclass
class MigrationInput:
    db: InfrahubDatabase
    at: Timestamp = field(default_factory=Timestamp)
    user_id: str = SYSTEM_USER_ID


class SchemaMigration(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    name: str = Field(..., description="Name of the migration")
    queries: Sequence[type[MigrationBaseQuery]] = Field(
        ..., description="List of queries to execute for this migration"
    )

    new_node_schema: MainSchemaTypes | None = None
    previous_node_schema: MainSchemaTypes | None = None
    schema_path: SchemaPath

    async def execute_pre_queries(
        self,
        migration_input: MigrationInput,  # noqa: ARG002
        result: MigrationResult,
        branch: Branch,  # noqa: ARG002
    ) -> MigrationResult:
        return result

    async def execute_post_queries(
        self,
        migration_input: MigrationInput,  # noqa: ARG002
        result: MigrationResult,
        branch: Branch,  # noqa: ARG002
    ) -> MigrationResult:
        return result

    async def execute_queries(
        self,
        migration_input: MigrationInput,
        result: MigrationResult,
        branch: Branch,
        queries: Sequence[type[MigrationBaseQuery]],
    ) -> MigrationResult:
        for migration_query in queries:
            try:
                query = await migration_query.init(
                    db=migration_input.db,
                    branch=branch,
                    at=migration_input.at,
                    migration=self,
                    user_id=migration_input.user_id,
                )
                await query.execute(db=migration_input.db)
                result.nbr_migrations_executed += query.get_nbr_migrations_executed()
            except Exception as exc:
                result.errors.append(str(exc))
                return result

        return result

    async def execute(
        self,
        migration_input: MigrationInput,
        branch: Branch,
        queries: Sequence[type[MigrationBaseQuery]] | None = None,
    ) -> MigrationResult:
        async with migration_input.db.start_transaction() as ts:
            result = MigrationResult()
            txn_migration_input = MigrationInput(db=ts, at=migration_input.at, user_id=migration_input.user_id)

            await self.execute_pre_queries(migration_input=txn_migration_input, result=result, branch=branch)
            queries_to_execute = queries or self.queries
            await self.execute_queries(
                migration_input=txn_migration_input, result=result, branch=branch, queries=queries_to_execute
            )
            await self.execute_post_queries(migration_input=txn_migration_input, result=result, branch=branch)

        return result

    @property
    def new_schema(self) -> MainSchemaTypes:
        if self.new_node_schema:
            return self.new_node_schema
        raise ValueError("new_node_schema hasn't been initialized")

    @property
    def previous_schema(self) -> MainSchemaTypes:
        if self.previous_node_schema:
            return self.previous_node_schema
        raise ValueError("previous_node_schema hasn't been initialized")


class AttributeSchemaMigration(SchemaMigration):
    uuids: list[str] | None = None

    @property
    def new_attribute_schema(self) -> AttributeSchema:
        if not self.schema_path.field_name:
            raise ValueError("field_name is not defined")
        return self.new_schema.get_attribute(name=self.schema_path.field_name)

    @property
    def previous_attribute_schema(self) -> AttributeSchema:
        if not self.schema_path.field_name:
            raise ValueError("field_name is not defined")
        return self.previous_schema.get_attribute(name=self.schema_path.field_name)


class RelationshipSchemaMigration(SchemaMigration):
    @property
    def new_relationship_schema(self) -> RelationshipSchema:
        if not self.schema_path.field_name:
            raise ValueError("field_name is not defined")
        return self.new_schema.get_relationship(name=self.schema_path.field_name)

    @property
    def previous_relationship_schema(self) -> RelationshipSchema:
        if not self.schema_path.field_name or not self.previous_node_schema:
            raise ValueError("field_name is not defined")
        return self.previous_schema.get_relationship(name=self.schema_path.field_name)


class GraphMigration(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    name: str = Field(..., description="Name of the migration")
    queries: Sequence[type[Query]] = Field(..., description="List of queries to execute for this migration")
    minimum_version: int = Field(..., description="Minimum version of the graph to execute this migration")

    @classmethod
    def init(cls, **kwargs: dict[str, Any]) -> Self:
        return cls(**kwargs)  # type: ignore[arg-type]

    async def validate_migration(self, db: InfrahubDatabase) -> MigrationResult:
        raise NotImplementedError

    async def execute(self, migration_input: MigrationInput) -> MigrationResult:
        async with migration_input.db.start_transaction() as ts:
            txn_migration_input = MigrationInput(db=ts, at=migration_input.at)
            return await self.do_execute(migration_input=txn_migration_input)

    async def do_execute(self, migration_input: MigrationInput) -> MigrationResult:
        result = MigrationResult()
        for migration_query in self.queries:
            try:
                query = await migration_query.init(db=migration_input.db, at=migration_input.at)
                await query.execute(db=migration_input.db)
            except Exception as exc:
                result.errors.append(str(exc))
                return result

        return result


class InternalSchemaMigration(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    name: str = Field(..., description="Name of the migration")
    migrations: Sequence[SchemaMigration] = Field(..., description="")
    minimum_version: int = Field(..., description="Minimum version of the graph to execute this migration")

    @staticmethod
    def get_internal_schema() -> SchemaBranch:
        from infrahub.core.schema.schema_branch import SchemaBranch

        # load the internal schema from
        schema = SchemaRoot(**internal_schema)
        schema_branch = SchemaBranch(cache={}, name="default_branch")
        schema_branch.load_schema(schema=schema)
        schema_branch.process()

        return schema_branch

    @classmethod
    def init(cls, **kwargs: dict[str, Any]) -> Self:
        return cls(**kwargs)  # type: ignore[arg-type]

    async def validate_migration(self, db: InfrahubDatabase) -> MigrationResult:
        raise NotImplementedError

    async def execute(self, migration_input: MigrationInput) -> MigrationResult:
        result = MigrationResult()

        default_branch = registry.get_branch_from_registry()

        for migration in self.migrations:
            try:
                execution_result = await migration.execute(migration_input=migration_input, branch=default_branch)
                result.errors.extend(execution_result.errors)
            except Exception as exc:
                result.errors.append(str(exc))
                return result

        return result


class ArbitraryMigration(BaseModel):
    name: str = Field(..., description="Name of the migration")
    minimum_version: int = Field(..., description="Minimum version of the graph to execute this migration")

    @classmethod
    def init(cls, **kwargs: dict[str, Any]) -> Self:
        return cls(**kwargs)  # type: ignore[arg-type]

    async def validate_migration(self, db: InfrahubDatabase) -> MigrationResult:
        raise NotImplementedError()

    async def execute(self, migration_input: MigrationInput) -> MigrationResult:
        raise NotImplementedError()


class MigrationRequiringRebase(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    name: str = Field(..., description="Name of the migration")
    minimum_version: int = Field(..., description="Minimum version of the graph to execute this migration")

    @classmethod
    def init(cls, **kwargs: dict[str, Any]) -> Self:
        return cls(**kwargs)  # type: ignore[arg-type]

    async def validate_migration(self, db: InfrahubDatabase) -> MigrationResult:
        raise NotImplementedError()

    async def execute_against_branch(self, migration_input: MigrationInput, branch: Branch) -> MigrationResult:
        """Method that will be run against non-default branches, it assumes that the branches have been rebased."""
        raise NotImplementedError()

    async def execute(self, migration_input: MigrationInput) -> MigrationResult:
        """Method that will be run against the default branch."""
        raise NotImplementedError()


type MigrationTypes = GraphMigration | InternalSchemaMigration | ArbitraryMigration | MigrationRequiringRebase
