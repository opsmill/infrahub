from typing import TYPE_CHECKING

from graphene import Boolean, InputObjectType, List, Mutation, String
from graphql import GraphQLResolveInfo

from infrahub.core.manager import NodeManager
from infrahub.exceptions import NodeNotFound

if TYPE_CHECKING:
    from neo4j import AsyncSession

# pylint: disable=unused-argument


class GroupMembersInput(InputObjectType):
    id = String(required=True)
    members = List(of_type=String)


class GroupMemberAdd(Mutation):
    class Arguments:
        data = GroupMembersInput(required=True)

    ok = Boolean()

    @classmethod
    async def mutate(
        cls,
        root: dict,
        info: GraphQLResolveInfo,
        data: GroupMembersInput,
    ):
        session: AsyncSession = info.context.get("infrahub_session")
        at = info.context.get("infrahub_at")
        branch = info.context.get("infrahub_branch")

        if not (
            group := await NodeManager.get_one(
                session=session, id=data.get("id"), branch=branch, at=at, include_owner=True, include_source=True
            )
        ):
            raise NodeNotFound(branch, "Group", data.get("id"))

        await group.members.add(session=session, nodes=data["members"])


class GroupMemberRemove(Mutation):
    class Arguments:
        data = GroupMembersInput(required=True)

    ok = Boolean()

    @classmethod
    async def mutate(
        cls,
        root: dict,
        info: GraphQLResolveInfo,
        data: GroupMembersInput,
    ):
        session: AsyncSession = info.context.get("infrahub_session")
        at = info.context.get("infrahub_at")
        branch = info.context.get("infrahub_branch")

        group = await NodeManager.get_one(session=session, id=data["id"], branch=branch, at=at)

        await group.members.remove(session=session, nodes=data["members"])
