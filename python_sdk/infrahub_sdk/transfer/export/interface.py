from abc import ABC, abstractmethod
from typing import List

from infrahub_sdk.node import InfrahubNode


class ExporterInterface(ABC):
    @abstractmethod
    async def export(self, nodes: List[InfrahubNode]) -> None:
        ...
