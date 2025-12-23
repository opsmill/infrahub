from dataclasses import dataclass

from infrahub.constants.enums import OrderDirection
from infrahub.exceptions import ValidationError


@dataclass
class NodeMetaOrder:
    created_at: OrderDirection | None = None
    updated_at: OrderDirection | None = None


@dataclass
class OrderModel:
    disable: bool | None = None
    node_metadata: NodeMetaOrder | None = None

    def validate(self) -> None:
        if self.node_metadata and self.node_metadata.created_at and self.node_metadata.updated_at:
            raise ValidationError("Cannot order by both created_at and updated_at simultaneously.")
