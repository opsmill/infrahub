from typing import Optional

from graphene import InputObjectType

from infrahub.core.branch import Branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.schema import MainSchemaTypes
from infrahub.database import InfrahubDatabase

from .interface import MutationNodeGetterInterface


class MutationNodeGetterByGuid(MutationNodeGetterInterface):
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
        if not node_schema.global_identifiers or "guid" not in data:
            return node

        return await self.node_manager.get_one_by_guid(
            db=self.db,
            guid=data["guid"],
            kind=node_schema.kind,
            branch=branch,
            at=at,
        )
