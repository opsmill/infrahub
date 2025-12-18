from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from infrahub.exceptions import ValidationError

if TYPE_CHECKING:
    from infrahub.constants.enums import OrderDirection


@dataclass
class NodeMetaOrder:
    created_at: OrderDirection | None = None
    updated_at: OrderDirection | None = None


@dataclass
class OrderModel:
    # Corresponds to infrahub.graphql.manager.OrderInput
    disable: bool | None = None
    node_metadata: NodeMetaOrder | None = None

    @classmethod
    def from_input(cls, input_data: dict[str, Any] | None) -> OrderModel | None:
        """Convert the dictionary type input data from GraphQL into an OrderModel instance."""
        if not input_data:
            return None

        order_model = cls(**input_data)
        order_model.validate()
        return order_model

    def validate(self) -> None:
        if self.node_metadata and self.node_metadata.created_at and self.node_metadata.updated_at:
            raise ValidationError("Cannot order by both created_at and updated_at simultaneously.")
