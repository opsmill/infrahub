from pydantic import BaseModel, ConfigDict, Field

from infrahub.core.branch import Branch
from infrahub.core.models import SchemaUpdateMigrationInfo
from infrahub.core.path import SchemaPath
from infrahub.core.schema.schema_branch import SchemaBranch


class SchemaApplyMigrationData(BaseModel):
    model_config = ConfigDict(
        arbitrary_types_allowed=True, json_encoders={SchemaBranch: SchemaBranch.to_dict_schema_object}
    )
    branch: Branch
    new_schema: SchemaBranch
    previous_schema: SchemaBranch
    migrations: list[SchemaUpdateMigrationInfo]


class SchemaMigrationPathResponseData(BaseModel):
    errors: list[str] = Field(default_factory=list)
    migration_name: str | None = None
    nbr_migrations_executed: int | None = None
    schema_path: SchemaPath | None = None
