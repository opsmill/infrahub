from __future__ import annotations

from typing import TYPE_CHECKING, Any, Sequence

from pydantic import BaseModel, ConfigDict, Field
from rich.console import Console
from typing_extensions import Self

from infrahub.auth import AccountSession, AuthType
from infrahub.context import InfrahubContext
from infrahub.core import registry
from infrahub.core.branch.enums import BranchStatus
from infrahub.core.path import SchemaPath  # noqa: TC001
from infrahub.core.query import Query  # noqa: TC001
from infrahub.core.schema import (
    AttributeSchema,
    MainSchemaTypes,
    RelationshipSchema,
    SchemaRoot,
    internal_schema,
)
from infrahub.core.timestamp import Timestamp
from infrahub.exceptions import ValidationError
from infrahub.lock import initialize_lock

from .query import MigrationBaseQuery  # noqa: TC001

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
        db: InfrahubDatabase,  # noqa: ARG002
        result: MigrationResult,
        branch: Branch,  # noqa: ARG002
        at: Timestamp,  # noqa: ARG002
    ) -> MigrationResult:
        return result

    async def execute_post_queries(
        self,
        db: InfrahubDatabase,  # noqa: ARG002
        result: MigrationResult,
        branch: Branch,  # noqa: ARG002
        at: Timestamp,  # noqa: ARG002
    ) -> MigrationResult:
        return result

    async def execute_queries(
        self,
        db: InfrahubDatabase,
        result: MigrationResult,
        branch: Branch,
        at: Timestamp,
        queries: Sequence[type[MigrationBaseQuery]],
    ) -> MigrationResult:
        for migration_query in queries:
            try:
                query = await migration_query.init(db=db, branch=branch, at=at, migration=self)
                await query.execute(db=db)
                result.nbr_migrations_executed += query.get_nbr_migrations_executed()
            except Exception as exc:
                result.errors.append(str(exc))
                return result

        return result

    async def execute(
        self,
        db: InfrahubDatabase,
        branch: Branch,
        at: Timestamp | str | None = None,
        queries: Sequence[type[MigrationBaseQuery]] | None = None,
    ) -> MigrationResult:
        async with db.start_transaction() as ts:
            result = MigrationResult()
            at = Timestamp(at)

            await self.execute_pre_queries(db=ts, result=result, branch=branch, at=at)
            queries_to_execute = queries or self.queries
            await self.execute_queries(db=ts, result=result, branch=branch, at=at, queries=queries_to_execute)
            await self.execute_post_queries(db=ts, result=result, branch=branch, at=at)

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

    async def execute(self, db: InfrahubDatabase) -> MigrationResult:
        async with db.start_transaction() as ts:
            return await self.do_execute(db=ts)

    async def do_execute(self, db: InfrahubDatabase) -> MigrationResult:
        result = MigrationResult()
        for migration_query in self.queries:
            try:
                query = await migration_query.init(db=db)
                await query.execute(db=db)
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

    async def execute(self, db: InfrahubDatabase) -> MigrationResult:
        result = MigrationResult()

        default_branch = registry.get_branch_from_registry()

        for migration in self.migrations:
            try:
                execution_result = await migration.execute(db=db, branch=default_branch)
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

    async def execute(self, db: InfrahubDatabase) -> MigrationResult:
        raise NotImplementedError()


class MigrationWithRebase(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    name: str = Field(..., description="Name of the migration")
    minimum_version: int = Field(..., description="Minimum version of the graph to execute this migration")

    @classmethod
    def init(cls, **kwargs: dict[str, Any]) -> Self:
        return cls(**kwargs)  # type: ignore[arg-type]

    async def rebase_branch(self, branch: Branch) -> bool:
        # Circular deps if imported inside import block
        from infrahub.core.branch.tasks import rebase_branch

        console = Console()
        console.print(f"Rebasing branch '{branch.name}' (ID: {branch.uuid})...", end="")
        try:
            await rebase_branch(
                branch=branch.name,
                context=InfrahubContext.init(
                    branch=branch, account=AccountSession(auth_type=AuthType.NONE, authenticated=False, account_id="")
                ),
                send_events=False,
            )
            console.print("done")
        except ValidationError:
            console.print("failed")
            return False

        return True

    async def validate_migration(self, db: InfrahubDatabase) -> MigrationResult:
        raise NotImplementedError()

    async def execute_against_branch(self, db: InfrahubDatabase, branch: Branch) -> MigrationResult:
        raise NotImplementedError()

    async def execute_against_branches(self, db: InfrahubDatabase, branches: Sequence[Branch]) -> MigrationResult:
        result = MigrationResult()

        for branch in branches:
            await registry.schema.load_schema(db=db, branch=branch)

            if not await self.rebase_branch(branch=branch):
                branch.status = BranchStatus.NEED_UPGRADE_REBASE
                await branch.save(db=db)
                continue

            r = await self.execute_against_branch(db=db, branch=branch)
            result.nbr_migrations_executed += 1
            if r.errors:
                result.errors.extend(r.errors)
            if r.success:
                branch.graph_version = self.minimum_version + 1
                await branch.save(db=db)

        return result

    async def execute(self, db: InfrahubDatabase) -> MigrationResult:
        from infrahub.core.initialization import initialization

        initialize_lock()
        await initialization(db=db)

        return await self.execute_against_branch(db=db, branch=registry.get_branch_from_registry())
