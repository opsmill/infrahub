from pydantic import BaseModel, ConfigDict

from infrahub.core.branch import Branch
from infrahub.core.models import SchemaUpdateConstraintInfo
from infrahub.core.schema_manager import SchemaBranch


class SchemaValidateMigrationData(BaseModel):
    model_config = ConfigDict(
        arbitrary_types_allowed=True, json_encoders={SchemaBranch: SchemaBranch.to_dict_schema_object}
    )
    branch: Branch
    schema_branch: SchemaBranch
    constraints: list[SchemaUpdateConstraintInfo]
