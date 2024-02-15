from abc import ABC, abstractmethod
from typing import List

from infrahub.core.path import GroupedDataPaths  # noqa: TCH001
from infrahub.message_bus.messages.schema_validator_path import SchemaValidatorPath

from .shared import SchemaValidatorQuery


class ConstraintCheckerInterface(ABC):
    query_classes: List[type[SchemaValidatorQuery]] = []

    @property
    @abstractmethod
    def name(self) -> str:
        ...

    @abstractmethod
    def supports(self, message: SchemaValidatorPath) -> bool:
        ...

    @abstractmethod
    async def check(self, message: SchemaValidatorPath) -> List[GroupedDataPaths]:
        ...
