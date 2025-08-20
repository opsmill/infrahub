from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_serializer

from infrahub.core.branch import Branch
from infrahub.core.models import SchemaUpdateMigrationInfo
from infrahub.core.path import SchemaPath
from infrahub.core.schema.schema_branch import SchemaBranch


class SchemaApplyMigrationData(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    branch: Branch
    new_schema: SchemaBranch
    previous_schema: SchemaBranch
    migrations: list[SchemaUpdateMigrationInfo]

    @model_serializer()
    def serialize_model(self) -> dict[str, Any]:
        return {
            "branch": self.branch.model_dump(),
            "previous_schema": self.previous_schema.to_dict_schema_object(),
            "new_schema": self.new_schema.to_dict_schema_object(),
            "migrations": [migration.model_dump() for migration in self.migrations],
        }

    @field_validator("new_schema", "previous_schema", mode="before")
    @classmethod
    def validate_schema_branch(cls, value: Any) -> SchemaBranch:
        return SchemaBranch.validate(data=value)


class SchemaMigrationPathResponseData(BaseModel):
    errors: list[str] = Field(default_factory=list)
    migration_name: str | None = None
    nbr_migrations_executed: int | None = None
    schema_path: SchemaPath | None = None
