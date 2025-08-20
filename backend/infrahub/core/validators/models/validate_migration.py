from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_serializer

from infrahub.core.branch import Branch
from infrahub.core.models import SchemaUpdateConstraintInfo
from infrahub.core.path import SchemaPath
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.core.validators.model import SchemaViolation
from infrahub.message_bus import InfrahubResponseData


class SchemaValidateMigrationData(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    branch: Branch
    schema_branch: SchemaBranch
    constraints: list[SchemaUpdateConstraintInfo]

    @model_serializer()
    def serialize_model(self) -> dict[str, Any]:
        return {
            "branch": self.branch.model_dump(),
            "schema_branch": self.schema_branch.to_dict_schema_object(),
            "constraints": [constraint.model_dump() for constraint in self.constraints],
        }

    @field_validator("schema_branch", mode="before")
    @classmethod
    def validate_schema_branch(cls, value: Any) -> SchemaBranch:
        return SchemaBranch.validate(data=value)


class SchemaValidatorPathResponseData(InfrahubResponseData):
    violations: list[SchemaViolation] = Field(default_factory=list)
    constraint_name: str
    schema_path: SchemaPath

    def get_messages(self) -> list[str]:
        return [violation.message for violation in self.violations]
