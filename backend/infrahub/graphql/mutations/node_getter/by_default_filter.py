from typing import Optional

from graphene import InputObjectType

from infrahub.core.branch import Branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.schema import MainSchemaTypes
from infrahub.database import InfrahubDatabase

from .interface import MutationNodeGetterInterface


class MutationNodeGetterByDefaultFilter(MutationNodeGetterInterface):
    def __init__(self, db: InfrahubDatabase, node_manager: NodeManager):
        self.db = db
        self.node_manager = node_manager

    async def get_node(
        self,
        node_schema: MainSchemaTypes,
        data: InputObjectType,
        branch: Branch,
        at: str,
    ) -> Optional[Node]:
        node = None
        default_filter_value = None
        if not node_schema.default_filter:
            return node
        this_datum = data

        for filter_key in node_schema.default_filter.split("__"):
            if filter_key not in this_datum:
                break
            this_datum = this_datum[filter_key]
        default_filter_value = this_datum

        if not default_filter_value:
            return node

        return await self.node_manager.get_one_by_default_filter(
            db=self.db,
            id=default_filter_value,
            schema_name=node_schema.kind,
            branch=branch,
            at=at,
        )
