from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_serializer

from infrahub.core.branch import Branch
from infrahub.core.path import SchemaPath
from infrahub.core.schema import GenericSchema, NodeSchema
from infrahub.core.schema.schema_branch import SchemaBranch


class SchemaConstraintValidatorRequest(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    branch: Branch = Field(..., description="The name of the branch to target")
    constraint_name: str = Field(..., description="The name of the constraint to validate")
    node_schema: NodeSchema | GenericSchema = Field(..., description="Schema of Node or Generic to validate")
    schema_path: SchemaPath = Field(..., description="SchemaPath to the element of the schema to validate")
    schema_branch: SchemaBranch = Field(..., description="SchemaBranch of the element to validate")

    @model_serializer()
    def serialize_model(self) -> dict[str, Any]:
        return {
            "branch": self.branch.model_dump(),
            "constraint_name": self.constraint_name,
            "node_schema": self.node_schema.model_dump(),
            "schema_path": self.schema_path.model_dump(),
            "schema_branch": self.schema_branch.to_dict_schema_object(),
        }

    @field_validator("schema_branch", mode="before")
    @classmethod
    def validate_schema_branch(cls, value: Any) -> SchemaBranch:
        return SchemaBranch.validate(data=value)


class SchemaViolation(BaseModel):
    node_id: str
    node_kind: str
    display_label: str
    full_display_label: str
    message: str = ""
