from __future__ import annotations

from typing import Union

from pydantic import Field

from infrahub.core.branch import Branch  # noqa: TCH001
from infrahub.core.schema import GenericSchema, NodeSchema  # noqa: TCH001
from infrahub.message_bus import InfrahubMessage, InfrahubResponse

from .schema_migration import SchemaMigrationResponseData  # noqa: TCH001

ROUTING_KEY = "schema.migration.attribute"


class SchemaMigrationAttribute(InfrahubMessage):
    branch: Branch = Field(..., description="The name of the branch to target")
    migration_name: str = Field(..., description="The name of the migration to run")
    node_schema: Union[NodeSchema, GenericSchema] = Field(..., description="Schema of Node or Generic to update")
    attribute_name: str = Field(..., description="Name of the attribute to add in the schema")


class SchemaMigrationAttributeResponse(InfrahubResponse):
    routing_key: str = ROUTING_KEY
    data: SchemaMigrationResponseData
