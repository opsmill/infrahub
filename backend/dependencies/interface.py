from abc import ABC, abstractmethod
from typing import Generic, TypeVar

T = TypeVar("T")


class DependencyBuilder(ABC, Generic[T]):
    @classmethod
    @abstractmethod
    def build(cls) -> T:
        ...
