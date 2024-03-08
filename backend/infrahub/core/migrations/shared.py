from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional, Sequence, Union

from pydantic import BaseModel, ConfigDict, Field

from infrahub.core.path import SchemaPath  # noqa: TCH001
from infrahub.core.schema import AttributeSchema, GenericSchema, NodeSchema, RelationshipSchema  # noqa: TCH001

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.query import Query
    from infrahub.core.timestamp import Timestamp
    from infrahub.database import InfrahubDatabase


class MigrationResult(BaseModel):
    errors: List[str] = Field(default_factory=list)

    @property
    def success(self) -> bool:
        if not self.errors:
            return True

        return False


class SchemaMigration(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    name: str = Field(..., description="Name of the migration")
    queries: Sequence[type[Query]] = Field(..., description="List of queries to execute for this migration")

    new_node_schema: Union[NodeSchema, GenericSchema]
    previous_node_schema: Union[NodeSchema, GenericSchema]
    schema_path: SchemaPath

    # async def validate_migration(self, db: InfrahubDatabase):
    #     raise NotImplementedError

    async def execute(
        self, db: InfrahubDatabase, branch: Branch, at: Optional[Union[Timestamp, str]] = None
    ) -> MigrationResult:
        async with db.start_transaction() as ts:
            result = MigrationResult()

            for migration_query in self.queries:
                try:
                    query = await migration_query.init(db=ts, branch=branch, at=at, migration=self)
                    await query.execute(db=ts)
                except Exception as exc:  # pylint: disable=broad-exception-caught
                    result.errors.append(str(exc))
                    return result

        return result


class AttributeSchemaMigration(SchemaMigration):
    @property
    def new_attribute_schema(self) -> AttributeSchema:
        if not self.schema_path.field_name:
            raise ValueError("field_name is not defined")
        return self.new_node_schema.get_attribute(name=self.schema_path.field_name)

    @property
    def previous_attribute_schema(self) -> AttributeSchema:
        if not self.schema_path.field_name:
            raise ValueError("field_name is not defined")
        return self.previous_node_schema.get_attribute(name=self.schema_path.field_name)


class RelationshipSchemaMigration(SchemaMigration):
    @property
    def new_relationship_schema(self) -> RelationshipSchema:
        if not self.schema_path.field_name:
            raise ValueError("field_name is not defined")
        return self.new_node_schema.get_relationship(name=self.schema_path.field_name)

    @property
    def previous_relationship_schema(self) -> RelationshipSchema:
        if not self.schema_path.field_name:
            raise ValueError("field_name is not defined")
        return self.previous_node_schema.get_relationship(name=self.schema_path.field_name)


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
