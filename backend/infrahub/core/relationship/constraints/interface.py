from abc import ABC, abstractmethod

from infrahub.core.node import Node
from infrahub.core.schema import MainSchemaTypes

from ..model import RelationshipManager


class RelationshipManagerConstraintInterface(ABC):
    @abstractmethod
    async def check(self, relm: RelationshipManager, node_schema: MainSchemaTypes, node: Node) -> None: ...

    def expand_filters(self, field_filters: list[str], node_schema: MainSchemaTypes) -> list[str]:  # noqa: ARG002
        """Expand field_filters to include additional relationships this constraint needs checked. Override in
        subclasses that need cross-field validation."""
        return field_filters
