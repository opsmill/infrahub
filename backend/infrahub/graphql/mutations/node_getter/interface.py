from abc import ABC, abstractmethod
from typing import Optional

from graphene import InputObjectType

from infrahub.core.branch import Branch
from infrahub.core.node import Node
from infrahub.core.schema import NodeSchema


class MutationNodeGetterInterface(ABC):
    @abstractmethod
    async def get_node(
        self,
        node_schema: NodeSchema,
        data: InputObjectType,
        branch: Branch,
        at: str,
    ) -> Optional[Node]:
        ...
