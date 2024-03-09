from __future__ import annotations

from typing import List, Union

from pydantic import Field

from infrahub.core.branch import Branch  # noqa: TCH001
from infrahub.core.path import SchemaPath  # noqa: TCH001
from infrahub.core.schema import GenericSchema, NodeSchema  # noqa: TCH001
from infrahub.message_bus import InfrahubMessage, InfrahubResponse, InfrahubResponseData

ROUTING_KEY = "schema.migration.path"


class SchemaMigrationPath(InfrahubMessage):
    branch: Branch = Field(..., description="The name of the branch to target")
    migration_name: str = Field(..., description="The name of the migration to run")
    new_node_schema: Union[NodeSchema, GenericSchema] = Field(
        ..., description="new Schema of Node or Generic to process"
    )
    previous_node_schema: Union[NodeSchema, GenericSchema] = Field(
        ..., description="Previous Schema of Node or Generic to process"
    )
    schema_path: SchemaPath = Field(..., description="SchemaPath to the element of the schema to migrate")


class SchemaMigrationPathResponseData(InfrahubResponseData):
    errors: List[str] = Field(default_factory=list)
    migration_name: str
    nbr_migrations_executed: int
    schema_path: SchemaPath


class SchemaMigrationPathResponse(InfrahubResponse):
    routing_key: str = ROUTING_KEY
    data: SchemaMigrationPathResponseData
