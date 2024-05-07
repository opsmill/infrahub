from __future__ import annotations

from typing import List, Optional

from pydantic import Field

from infrahub.core.branch import Branch  # noqa: TCH001
from infrahub.core.path import SchemaPath  # noqa: TCH001
from infrahub.core.schema import MainSchemaTypes  # noqa: TCH001
from infrahub.message_bus import InfrahubMessage, InfrahubResponse, InfrahubResponseData

ROUTING_KEY = "schema.migration.path"


class SchemaMigrationPath(InfrahubMessage):
    branch: Branch = Field(..., description="The name of the branch to target")
    migration_name: str = Field(..., description="The name of the migration to run")
    new_node_schema: Optional[MainSchemaTypes] = Field(None, description="new Schema of Node or Generic to process")
    previous_node_schema: Optional[MainSchemaTypes] = Field(
        None, description="Previous Schema of Node or Generic to process"
    )
    schema_path: SchemaPath = Field(..., description="SchemaPath to the element of the schema to migrate")


class SchemaMigrationPathResponseData(InfrahubResponseData):
    errors: List[str] = Field(default_factory=list)
    migration_name: Optional[str] = None
    nbr_migrations_executed: Optional[int] = None
    schema_path: Optional[SchemaPath] = None


class SchemaMigrationPathResponse(InfrahubResponse):
    routing_key: str = ROUTING_KEY
    data: SchemaMigrationPathResponseData
