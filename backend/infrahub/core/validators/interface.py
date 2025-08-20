from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from infrahub.core.path import GroupedDataPaths

    from .model import SchemaConstraintValidatorRequest


class ConstraintCheckerInterface(ABC):
    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def supports(self, request: SchemaConstraintValidatorRequest) -> bool: ...

    @abstractmethod
    async def check(self, request: SchemaConstraintValidatorRequest) -> list[GroupedDataPaths]: ...
