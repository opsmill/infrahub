from abc import ABC, abstractmethod

from graphene import InputObjectType

from infrahub.core.branch import Branch
from infrahub.core.node import Node
from infrahub.core.schema import MainSchemaTypes


class MutationNodeGetterInterface(ABC):
    @abstractmethod
    async def get_node(
        self,
        node_schema: MainSchemaTypes,
        data: InputObjectType,
        branch: Branch,
    ) -> Node | None: ...
