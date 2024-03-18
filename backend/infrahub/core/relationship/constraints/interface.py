from abc import ABC, abstractmethod

from ..model import RelationshipManager


class RelationshipManagerConstraintInterface(ABC):
    @abstractmethod
    async def check(self, relm: RelationshipManager) -> None: ...
