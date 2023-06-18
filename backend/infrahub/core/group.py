from __future__ import annotations

import enum
from typing import TYPE_CHECKING, Dict, List, Union

from infrahub.core.node import Node
from infrahub.core.query.group import (
    GroupAddAssociationQuery,
    GroupGetAssociationQuery,
    GroupHasAssociationQuery,
)

if TYPE_CHECKING:
    from neo4j import AsyncSession


class GroupAssociationType(str, enum.Enum):
    MEMBER = "member"
    SUBSCRIBER = "subscriber"


def extract_node_ids(nodes: Union[Node, str, List[Node], List[str]]) -> List[str]:
    node_ids: List[str] = []

    if not isinstance(nodes, list):
        nodes = [nodes]

    for node in nodes:
        if isinstance(node, Node):
            node_ids.append(node.id)
        elif isinstance(node, str):
            node_ids.append(node)

    return node_ids


class GroupAssociation:
    def __init__(self, association_type: GroupAssociationType, group: Group):
        self.association_type = association_type
        self.group = group

    async def get(self, session: AsyncSession) -> List[str]:
        query = await GroupGetAssociationQuery.init(
            session=session, association_type=self.association_type, group=self.group, branch=self.group._branch
        )
        await query.execute(session=session)
        return await query.get_members()

    async def has(self, session, nodes: Union[Node, str, List[Node], List[str]]) -> Dict[str, bool]:
        node_ids = extract_node_ids(nodes=nodes)
        query = await GroupHasAssociationQuery.init(
            session=session,
            association_type=self.association_type,
            group=self.group,
            node_ids=node_ids,
            branch=self.group._branch,
        )
        await query.execute(session=session)

        return await query.get_memberships()

    async def add(self, session: AsyncSession, nodes: Union[Node, str, List[Node], List[str]]):
        node_ids = extract_node_ids(nodes=nodes)

        memberships = await self.has(session=session, nodes=node_ids)

        node_ids_to_add = [node for node in node_ids if node in memberships and memberships[node] is False]

        query = await GroupAddAssociationQuery.init(
            session=session,
            association_type=self.association_type,
            group=self.group,
            node_ids=node_ids_to_add,
            branch=self.group._branch,
        )
        await query.execute(session=session)

    async def remove(self, session: AsyncSession, nodes: Union[Node, List[Node]]):
        node_ids = extract_node_ids(nodes=nodes)
        memberships = await self.has(session=session, nodes=node_ids)

        [node for node in node_ids if node in memberships and memberships[node] is True]

        # query = await GroupGetAssociationQuery.init(
        #     association_type=self.association_type,
        #     group=self.group,
        #     node_ids=node_ids_to_add,
        #     branch=self.group._branch
        # )
        # await query.execute()
        # return await query.get_members()


class Group(Node):
    def __init__(self, *args, **kwargs):
        self.members = GroupAssociation(group=self, association_type=GroupAssociationType.MEMBER)
        self.subcribers = GroupAssociation(group=self, association_type=GroupAssociationType.SUBSCRIBER)

        super().__init__(*args, **kwargs)
