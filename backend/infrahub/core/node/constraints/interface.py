from abc import ABC, abstractmethod

from infrahub.core.node import Node
from infrahub.core.timestamp import Timestamp


class NodeConstraintInterface(ABC):
    @abstractmethod
    async def check(self, node: Node, at: Timestamp | None = None, filters: list[str] | None = None) -> None: ...
