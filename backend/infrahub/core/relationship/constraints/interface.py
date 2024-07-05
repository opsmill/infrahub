from abc import ABC, abstractmethod

from infrahub.core.schema import MainSchemaTypes

from ..model import RelationshipManager


class RelationshipManagerConstraintInterface(ABC):
    @abstractmethod
    async def check(self, relm: RelationshipManager, node_schema: MainSchemaTypes) -> None: ...
