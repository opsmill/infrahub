from __future__ import annotations

from typing import List, Union

from pydantic import Field

from infrahub.core.branch import Branch  # noqa: TCH001
from infrahub.core.schema import GenericSchema, NodeSchema  # noqa: TCH001
from infrahub.core.validators.shared import SchemaViolation  # noqa: TCH001
from infrahub.message_bus import InfrahubMessage, InfrahubResponse, InfrahubResponseData

ROUTING_KEY = "schema.validator.attribute"


class SchemaValidatorAttribute(InfrahubMessage):
    branch: Branch = Field(..., description="The name of the branch to target")
    constraint_name: str = Field(..., description="The name of the constraint to validate")
    node_schema: Union[NodeSchema, GenericSchema] = Field(..., description="Schema of Node or Generic to validate")
    attribute_name: str = Field(..., description="Name of the attribute to validate in the schema")


class SchemaValidatorAttributeResponseData(InfrahubResponseData):
    violations: List[SchemaViolation] = Field(default_factory=list)


class SchemaValidatorAttributeResponse(InfrahubResponse):
    routing_key: str = ROUTING_KEY
    data: SchemaValidatorAttributeResponseData
