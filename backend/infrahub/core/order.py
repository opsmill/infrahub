from __future__ import annotations

from typing import Self

from pydantic import BaseModel, model_validator

from infrahub.constants.enums import OrderDirection  # noqa: TC001
from infrahub.exceptions import ValidationError

# Metadata field name constants
METADATA_CREATED_AT = "created_at"
METADATA_CREATED_BY = "created_by"
METADATA_UPDATED_AT = "updated_at"
METADATA_UPDATED_BY = "updated_by"


class NodeMetaOrder(BaseModel):
    created_at: OrderDirection | None = None
    updated_at: OrderDirection | None = None


class OrderModel(BaseModel):
    disable: bool | None = None
    node_metadata: NodeMetaOrder | None = None

    @model_validator(mode="after")
    def validate_metadata(self) -> Self:
        if self.node_metadata and self.node_metadata.created_at and self.node_metadata.updated_at:
            raise ValidationError("Cannot order by both created_at and updated_at simultaneously.")
        return self
