from abc import ABC, abstractmethod
from typing import List

from infrahub.core.path import GroupedDataPaths  # noqa: TCH001

from .model import SchemaConstraintValidatorRequest


class ConstraintCheckerInterface(ABC):
    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def supports(self, request: SchemaConstraintValidatorRequest) -> bool: ...

    @abstractmethod
    async def check(self, request: SchemaConstraintValidatorRequest) -> List[GroupedDataPaths]: ...
