from typing import Union

from pydantic import BaseModel, Field

from infrahub.core.branch import Branch
from infrahub.core.path import SchemaPath
from infrahub.core.schema import GenericSchema, NodeSchema


class SchemaConstraintValidatorRequest(BaseModel):
    branch: Branch = Field(..., description="The name of the branch to target")
    constraint_name: str = Field(..., description="The name of the constraint to validate")
    node_schema: Union[NodeSchema, GenericSchema] = Field(..., description="Schema of Node or Generic to validate")
    schema_path: SchemaPath = Field(..., description="SchemaPath to the element of the schema to validate")


class SchemaViolation(BaseModel):
    node_id: str
    node_kind: str
    display_label: str
    full_display_label: str
    message: str = ""
