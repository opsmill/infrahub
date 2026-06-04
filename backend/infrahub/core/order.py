from __future__ import annotations

from typing import Self

from pydantic import BaseModel, ConfigDict, model_validator

from infrahub.constants.enums import OrderDirection  # noqa: TC001
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


class OrderModel(BaseModel):
    model_config = ConfigDict(frozen=True)

    disable: bool | None = None
    node_metadata: NodeMetaOrder | None = None
    order_by: tuple[str, ...] | None = None

    def __bool__(self) -> bool:
        return bool(self.disable) or self.has_explicit_entries

    @property
    def has_explicit_entries(self) -> bool:
        """True when the model carries override ordering entries (metadata or order_by)."""
        return bool(self.node_metadata) or bool(self.order_by)

    @model_validator(mode="after")
    def validate_metadata(self) -> Self:
        if self.node_metadata and self.node_metadata.created_at and self.node_metadata.updated_at:
            raise ValidationError("Cannot order by both created_at and updated_at simultaneously.")
        if self.node_metadata and self.order_by:
            raise ValidationError(
                "Cannot combine 'node_metadata' and 'order_by' in the same order input. "
                "'order_by' supports node_metadata ordering options."
            )
        return self
