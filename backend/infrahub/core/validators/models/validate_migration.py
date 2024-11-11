from pydantic import BaseModel, ConfigDict, Field

from infrahub.core.branch import Branch
from infrahub.core.models import SchemaUpdateConstraintInfo
from infrahub.core.path import SchemaPath
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.core.validators.model import SchemaViolation
from infrahub.message_bus import InfrahubResponseData


class SchemaValidateMigrationData(BaseModel):
    model_config = ConfigDict(
        arbitrary_types_allowed=True, json_encoders={SchemaBranch: SchemaBranch.to_dict_schema_object}
    )
    branch: Branch
    schema_branch: SchemaBranch
    constraints: list[SchemaUpdateConstraintInfo]


class SchemaValidatorPathResponseData(InfrahubResponseData):
    violations: list[SchemaViolation] = Field(default_factory=list)
    constraint_name: str
    schema_path: SchemaPath

    def get_messages(self) -> list[str]:
        return [violation.message for violation in self.violations]
