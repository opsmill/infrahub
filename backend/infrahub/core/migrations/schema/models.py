from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator

from infrahub.core.branch import Branch
from infrahub.core.constants import SYSTEM_USER_ID
from infrahub.core.models import SchemaUpdateMigrationInfo
from infrahub.core.path import SchemaPath
from infrahub.core.schema.schema_branch import SchemaBranch, SchemaBranchDict
from infrahub.core.timestamp import Timestamp


class SchemaApplyMigrationData(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    branch: Branch
    new_schema: SchemaBranch
    previous_schema: SchemaBranch
    migrations: list[SchemaUpdateMigrationInfo]
    at: Timestamp
    user_id: str = SYSTEM_USER_ID
    application_id: str | None = None

    @field_serializer("branch")
    def serialize_branch(self, branch: Branch) -> dict[str, Any]:
        return branch.model_dump()

    @field_serializer("previous_schema", "new_schema")
    def serialize_schema_branch(self, schema: SchemaBranch) -> SchemaBranchDict:
        return schema.to_dict_schema_object()

    @field_serializer("at")
    def serialize_at(self, at: Timestamp) -> str:
        return at.to_string()

    @field_validator("new_schema", "previous_schema", mode="before")
    @classmethod
    def validate_schema_branch(cls, value: Any) -> SchemaBranch:
        return SchemaBranch.validate(data=value)

    @field_validator("at", mode="before")
    @classmethod
    def validate_at(cls, value: Any) -> Timestamp:
        return Timestamp(value)


class SchemaMigrationPathResponseData(BaseModel):
    errors: list[str] = Field(default_factory=list)
    migration_name: str
    nbr_migrations_executed: int | None = None
    schema_path: SchemaPath
