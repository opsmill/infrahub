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
    node_uuids: set[str] | None = Field(
        default=None,
        description=(
            "Optional set of node UUIDs to scope the validation to. When provided, "
            "checkers may pre-fetch current values for these nodes and run a "
            "narrowed query instead of scanning every node of the kind. None means "
            "fall back to the full-scan path (required for schema-diff-driven "
            "constraint changes)."
        ),
    )

    @model_serializer()
    def serialize_model(self) -> dict[str, Any]:
        return {
            "branch": self.branch.model_dump(),
            "constraint_name": self.constraint_name,
            "node_schema": self.node_schema.model_dump(),
            "schema_path": self.schema_path.model_dump(),
            "schema_branch": self.schema_branch.to_dict_schema_object(),
            "node_uuids": list(self.node_uuids) if self.node_uuids is not None else None,
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
