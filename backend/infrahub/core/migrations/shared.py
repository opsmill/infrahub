from __future__ import annotations

from typing import TYPE_CHECKING, Any, Sequence

from pydantic import BaseModel, ConfigDict, Field
from typing_extensions import Self

from infrahub.core import registry
from infrahub.core.path import SchemaPath  # noqa: TC001
from infrahub.core.query import Query  # noqa: TC001
from infrahub.core.schema import (
    AttributeSchema,
    GenericSchema,
    NodeSchema,
    RelationshipSchema,
    SchemaRoot,
    internal_schema,
)

from .query import MigrationQuery  # noqa: TC001

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.core.timestamp import Timestamp
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
    queries: Sequence[type[MigrationQuery]] = Field(..., description="List of queries to execute for this migration")

    new_node_schema: NodeSchema | GenericSchema | None = None
    previous_node_schema: NodeSchema | GenericSchema | None = None
    schema_path: SchemaPath

    async def execute(self, db: InfrahubDatabase, branch: Branch, at: Timestamp | str | None = None) -> MigrationResult:
        async with db.start_transaction() as ts:
            result = MigrationResult()

            for migration_query in self.queries:
                try:
                    query = await migration_query.init(db=ts, branch=branch, at=at, migration=self)
                    await query.execute(db=ts)
                    result.nbr_migrations_executed += query.get_nbr_migrations_executed()
                except Exception as exc:
                    result.errors.append(str(exc))
                    return result

        return result

    @property
    def new_schema(self) -> NodeSchema | GenericSchema:
        if self.new_node_schema:
            return self.new_node_schema
        raise ValueError("new_node_schema hasn't been initialized")

    @property
    def previous_schema(self) -> NodeSchema | GenericSchema:
        if self.previous_node_schema:
            return self.previous_node_schema
        raise ValueError("previous_node_schema hasn't been initialized")


class AttributeSchemaMigration(SchemaMigration):
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
