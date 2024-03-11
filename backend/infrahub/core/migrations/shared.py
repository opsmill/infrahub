from __future__ import annotations

from typing import TYPE_CHECKING, Any, List, Optional, Sequence, Union

from pydantic import BaseModel, ConfigDict, Field

from infrahub.core.path import SchemaPath  # noqa: TCH001
from infrahub.core.query import Query, QueryType
from infrahub.core.schema import AttributeSchema, GenericSchema, NodeSchema, RelationshipSchema  # noqa: TCH001

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.timestamp import Timestamp
    from infrahub.database import InfrahubDatabase


class MigrationResult(BaseModel):
    errors: List[str] = Field(default_factory=list)
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

    new_node_schema: Optional[Union[NodeSchema, GenericSchema]] = None
    previous_node_schema: Optional[Union[NodeSchema, GenericSchema]] = None
    schema_path: SchemaPath

    async def execute(
        self, db: InfrahubDatabase, branch: Branch, at: Optional[Union[Timestamp, str]] = None
    ) -> MigrationResult:
        async with db.start_transaction() as ts:
            result = MigrationResult()

            for migration_query in self.queries:
                try:
                    query = await migration_query.init(db=ts, branch=branch, at=at, migration=self)
                    await query.execute(db=ts)
                    result.nbr_migrations_executed += query.get_nbr_migrations_executed()
                except Exception as exc:  # pylint: disable=broad-exception-caught
                    result.errors.append(str(exc))
                    return result

        return result

    @property
    def new_schema(self) -> Union[NodeSchema, GenericSchema]:
        if self.new_node_schema:
            return self.new_node_schema
        raise ValueError("new_node_schema hasn't been initialized")

    @property
    def previous_schema(self) -> Union[NodeSchema, GenericSchema]:
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

    async def validate_migration(self, db: InfrahubDatabase) -> MigrationResult:
        raise NotImplementedError

    async def execute(self, db: InfrahubDatabase) -> MigrationResult:
        async with db.start_transaction() as ts:
            result = MigrationResult()

            for migration_query in self.queries:
                try:
                    query = await migration_query.init(db=ts)
                    await query.execute(db=ts)
                except Exception as exc:  # pylint: disable=broad-exception-caught
                    result.errors.append(str(exc))
                    return result

        return result


class MigrationQuery(Query):
    type: QueryType = QueryType.WRITE

    def __init__(
        self,
        migration: SchemaMigration,
        **kwargs: Any,
    ):
        self.migration = migration
        super().__init__(**kwargs)

    def get_nbr_migrations_executed(self) -> int:
        return self.num_of_results


class AttributeMigrationQuery(Query):
    type: QueryType = QueryType.WRITE

    def __init__(
        self,
        migration: AttributeSchemaMigration,
        **kwargs: Any,
    ):
        self.migration = migration
        super().__init__(**kwargs)

    def get_nbr_migrations_executed(self) -> int:
        return self.num_of_results
