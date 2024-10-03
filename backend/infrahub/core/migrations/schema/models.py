from pydantic import BaseModel, ConfigDict

from infrahub.core.branch import Branch
from infrahub.core.models import SchemaUpdateMigrationInfo
from infrahub.core.schema.schema_branch import SchemaBranch


class SchemaApplyMigrationData(BaseModel):
    model_config = ConfigDict(
        arbitrary_types_allowed=True, json_encoders={SchemaBranch: SchemaBranch.to_dict_schema_object}
    )
    branch: Branch
    new_schema: SchemaBranch
    previous_schema: SchemaBranch
    migrations: list[SchemaUpdateMigrationInfo]
