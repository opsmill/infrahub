from __future__ import annotations

from pydantic import Field

from infrahub.core.branch import Branch  # noqa: TCH001
from infrahub.core.path import SchemaPath  # noqa: TCH001
from infrahub.core.schema import MainSchemaTypes  # noqa: TCH001
from infrahub.core.validators.model import SchemaViolation  # noqa: TCH001
from infrahub.message_bus import InfrahubMessage, InfrahubResponse, InfrahubResponseData

ROUTING_KEY = "schema.validator.path"


class SchemaValidatorPath(InfrahubMessage):
    branch: Branch = Field(..., description="The name of the branch to target")
    constraint_name: str = Field(..., description="The name of the constraint to validate")
    node_schema: MainSchemaTypes = Field(..., description="Schema of Node or Generic to validate")
    schema_path: SchemaPath = Field(..., description="SchemaPath to the element of the schema to validate")


class SchemaValidatorPathResponseData(InfrahubResponseData):
    violations: list[SchemaViolation] = Field(default_factory=list)
    constraint_name: str
    schema_path: SchemaPath


class SchemaValidatorPathResponse(InfrahubResponse):
    routing_key: str = ROUTING_KEY
    data: SchemaValidatorPathResponseData
