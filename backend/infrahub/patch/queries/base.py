from abc import ABC, abstractmethod

from infrahub.database import InfrahubDatabase

from ..models import PatchPlan


class PatchQuery(ABC):
    def __init__(self, db: InfrahubDatabase):
        self.db = db

    @abstractmethod
    async def plan(self) -> PatchPlan: ...

    @property
    @abstractmethod
    def name(self) -> str: ...
