from abc import ABC, abstractmethod

from ..model import RelationshipManager, RelationshipUpdateDetails


class RelationshipManagerConstraintInterface(ABC):
    @abstractmethod
    async def check(self, relm: RelationshipManager, update_details: RelationshipUpdateDetails) -> None: ...
