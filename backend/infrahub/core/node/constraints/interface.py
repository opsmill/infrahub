from abc import ABC, abstractmethod
from typing import List, Optional

from infrahub.core.node import Node
from infrahub.core.timestamp import Timestamp


class NodeConstraintInterface(ABC):
    @abstractmethod
    async def check(self, node: Node, at: Optional[Timestamp] = None, filters: Optional[List[str]] = None) -> None:
        ...
