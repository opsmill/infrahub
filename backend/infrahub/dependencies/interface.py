from abc import ABC, abstractmethod
from typing import Generic, Optional, TypeVar

from infrahub.core.branch import Branch
from infrahub.database import InfrahubDatabase

T = TypeVar("T")


class DependencyBuilder(ABC, Generic[T]):
    @classmethod
    @abstractmethod
    def build(cls, db: InfrahubDatabase, branch: Optional[Branch] = None) -> T:
        ...
