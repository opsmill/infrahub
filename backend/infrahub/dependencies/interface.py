from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Generic, TypeVar

from infrahub.core.branch import Branch
from infrahub.database import InfrahubDatabase

T = TypeVar("T")


@dataclass
class DependencyBuilderContext:
    db: InfrahubDatabase
    branch: Branch


class DependencyBuilder(ABC, Generic[T]):
    @classmethod
    @abstractmethod
    def build(cls, context: DependencyBuilderContext) -> T: ...
