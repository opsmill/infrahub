from __future__ import annotations

from typing import Any, List, Optional

from pydantic import Field

from infrahub.core.constants import (
    DEFAULT_DESCRIPTION_LENGTH,
    DEFAULT_NAME_MAX_LENGTH,
    DEFAULT_NAME_MIN_LENGTH,
    NAME_REGEX,
    BranchSupportType,
    UpdateSupport,
)
from infrahub.core.models import HashableModel
from infrahub.core.schema.dropdown import DropdownChoice  # noqa: TCH001


class GeneratedAttributeSchema(HashableModel):
    id: Optional[str] = Field(default=None, json_schema_extra={"update": UpdateSupport.NOT_APPLICABLE.value})
    name: str = Field(
        pattern=NAME_REGEX,
        min_length=DEFAULT_NAME_MIN_LENGTH,
        max_length=DEFAULT_NAME_MAX_LENGTH,
        json_schema_extra={"update": UpdateSupport.NOT_SUPPORTED.value},
    )
    kind: str = Field(json_schema_extra={"update": UpdateSupport.MIGRATION_REQUIRED.value})  # AttributeKind
    label: Optional[str] = Field(default=None, json_schema_extra={"update": UpdateSupport.ALLOWED.value})
    description: Optional[str] = Field(
        default=None, max_length=DEFAULT_DESCRIPTION_LENGTH, json_schema_extra={"update": UpdateSupport.ALLOWED.value}
    )
    default_value: Optional[Any] = Field(default=None, json_schema_extra={"update": UpdateSupport.ALLOWED.value})
    enum: Optional[List] = Field(default=None, json_schema_extra={"update": UpdateSupport.VALIDATE_CONSTRAINT.value})
    regex: Optional[str] = Field(default=None, json_schema_extra={"update": UpdateSupport.VALIDATE_CONSTRAINT.value})
    max_length: Optional[int] = Field(
        default=None, json_schema_extra={"update": UpdateSupport.VALIDATE_CONSTRAINT.value}
    )
    min_length: Optional[int] = Field(
        default=None, json_schema_extra={"update": UpdateSupport.VALIDATE_CONSTRAINT.value}
    )
    read_only: bool = Field(default=False, json_schema_extra={"update": UpdateSupport.ALLOWED.value})
    inherited: bool = Field(default=False, json_schema_extra={"update": UpdateSupport.NOT_APPLICABLE.value})
    unique: bool = Field(default=False, json_schema_extra={"update": UpdateSupport.VALIDATE_CONSTRAINT.value})
    branch: Optional[BranchSupportType] = Field(
        default=None, json_schema_extra={"update": UpdateSupport.MIGRATION_REQUIRED.value}
    )
    optional: bool = Field(default=False, json_schema_extra={"update": UpdateSupport.VALIDATE_CONSTRAINT.value})
    order_weight: Optional[int] = Field(default=None, json_schema_extra={"update": UpdateSupport.ALLOWED.value})
    choices: Optional[List[DropdownChoice]] = Field(
        default=None,
        description="The available choices if the kind is Dropdown.",
        json_schema_extra={"update": UpdateSupport.VALIDATE_CONSTRAINT.value},
    )
