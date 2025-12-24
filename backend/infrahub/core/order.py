from __future__ import annotations

from typing import TYPE_CHECKING, Self

from pydantic import BaseModel, model_validator

from infrahub.exceptions import ValidationError

if TYPE_CHECKING:
    from infrahub.constants.enums import OrderDirection


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
