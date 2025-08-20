from copy import copy

from graphene import InputObjectType

from infrahub.core.branch import Branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.schema import MainSchemaTypes
from infrahub.database import InfrahubDatabase

from .interface import MutationNodeGetterInterface


class MutationNodeGetterByDefaultFilter(MutationNodeGetterInterface):
    def __init__(self, db: InfrahubDatabase, node_manager: NodeManager) -> None:
        self.db = db
        self.node_manager = node_manager

    async def get_node(
        self,
        node_schema: MainSchemaTypes,
        data: InputObjectType,
        branch: Branch,
    ) -> Node | None:
        if not node_schema.default_filter:
            return None

        data = copy(data)

        for filter_key in node_schema.default_filter.split("__"):
            if filter_key not in data:
                break
            data = data[filter_key]

        default_filter_value = data

        if not default_filter_value:
            return None

        return await self.node_manager.get_one_by_default_filter(
            db=self.db,
            id=default_filter_value,
            kind=node_schema.kind,
            branch=branch,
        )
