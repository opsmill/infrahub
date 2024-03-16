from __future__ import annotations

from typing import List, Optional, Union

from pydantic import Field

from infrahub.core.branch import Branch  # noqa: TCH001
from infrahub.core.path import SchemaPath  # noqa: TCH001
from infrahub.core.schema import GenericSchema, NodeSchema  # noqa: TCH001
from infrahub.core.validators.model import SchemaViolation  # noqa: TCH001
from infrahub.message_bus import InfrahubMessage, InfrahubResponse, InfrahubResponseData

ROUTING_KEY = "schema.validator.path"


class SchemaValidatorPath(InfrahubMessage):
    branch: Branch = Field(..., description="The name of the branch to target")
    constraint_name: str = Field(..., description="The name of the constraint to validate")
    node_schema: Union[NodeSchema, GenericSchema] = Field(..., description="Schema of Node or Generic to validate")
    schema_path: SchemaPath = Field(..., description="SchemaPath to the element of the schema to validate")


class SchemaValidatorPathResponseData(InfrahubResponseData):
    violations: List[SchemaViolation] = Field(default_factory=list)
    constraint_name: Optional[str] = None
    schema_path: Optional[SchemaPath] = None


class SchemaValidatorPathResponse(InfrahubResponse):
    routing_key: str = ROUTING_KEY
    data: SchemaValidatorPathResponseData
