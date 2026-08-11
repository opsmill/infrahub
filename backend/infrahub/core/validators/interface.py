from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from infrahub.core.path import GroupedDataPaths

    from .model import SchemaConstraintValidatorRequest


class ConstraintCheckerInterface(ABC):
    # Whether a change to instance data (as opposed to schema) can cause this constraint to be
    # violated. If the checker only compares schemas, it should set this False.
    triggered_by_data_change: bool = True

    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def supports(self, request: SchemaConstraintValidatorRequest) -> bool: ...

    @abstractmethod
    async def check(self, request: SchemaConstraintValidatorRequest) -> list[GroupedDataPaths]: ...
