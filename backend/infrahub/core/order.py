from __future__ import annotations

from dataclasses import dataclass
from typing import Self

from pydantic import BaseModel, ConfigDict, model_validator

from infrahub.constants.enums import OrderDirection
from infrahub.exceptions import ValidationError

# Metadata field name constants
METADATA_CREATED_AT = "created_at"
METADATA_CREATED_BY = "created_by"
METADATA_UPDATED_AT = "updated_at"
METADATA_UPDATED_BY = "updated_by"


class NodeMetaOrder(BaseModel):
    model_config = ConfigDict(frozen=True)

    created_at: OrderDirection | None = None
    updated_at: OrderDirection | None = None

    def __bool__(self) -> bool:
        return self.created_at is not None or self.updated_at is not None


class OrderByEntry(BaseModel):
    model_config = ConfigDict(frozen=True)

    field: str
    direction: OrderDirection = OrderDirection.ASC


@dataclass(frozen=True)
class AttributeValuePriority:
    attribute: str
    value: str


class OrderModel(BaseModel):
    model_config = ConfigDict(frozen=True)

    disable: bool | None = None
    node_metadata: NodeMetaOrder | None = None
    by: tuple[OrderByEntry, ...] | None = None
    priority: AttributeValuePriority | None = None

    def __bool__(self) -> bool:
        return bool(self.disable) or self.has_explicit_entries

    @property
    def has_explicit_entries(self) -> bool:
        """True when the model carries override ordering entries."""
        return bool(self.node_metadata) or bool(self.by) or self.priority is not None

    @model_validator(mode="after")
    def validate_metadata(self) -> Self:
        if self.priority is not None and (self.disable or self.node_metadata or self.by):
            raise ValidationError("Cannot combine attribute value priority with another order.")
        if self.node_metadata and self.node_metadata.created_at and self.node_metadata.updated_at:
            raise ValidationError("Cannot order by both created_at and updated_at simultaneously.")
        if self.node_metadata and self.by:
            raise ValidationError(
                "Cannot combine the deprecated 'node_metadata' and 'by' in the same order input. "
                "'by' supports node_metadata ordering options via the 'node_metadata__created_at' / "
                "'node_metadata__updated_at' fields."
            )
        return self
