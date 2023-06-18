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


class GroupSubscribersInput(InputObjectType):
    id = String(required=True)
    subscribers = List(of_type=String)


class GroupAssociationMixin:
    @classmethod
    async def mutate(
        cls,
        root: dict,
        info: GraphQLResolveInfo,
        data,
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

        if cls.__name__ == "GroupMemberAdd":
            await group.members.add(session=session, nodes=data["members"])
        elif cls.__name__ == "GroupMemberRemove":
            await group.members.remove(session=session, nodes=data["members"])
        elif cls.__name__ == "GroupSubscriberAdd":
            await group.subscribers.add(session=session, nodes=data["subscribers"])
        elif cls.__name__ == "GroupSubscriberRemove":
            await group.subscribers.remove(session=session, nodes=data["subscribers"])


class GroupMemberAdd(GroupAssociationMixin, Mutation):
    class Arguments:
        data = GroupMembersInput(required=True)

    ok = Boolean()


class GroupMemberRemove(GroupAssociationMixin, Mutation):
    class Arguments:
        data = GroupMembersInput(required=True)

    ok = Boolean()


class GroupSubscriberAdd(GroupAssociationMixin, Mutation):
    class Arguments:
        data = GroupSubscribersInput(required=True)

    ok = Boolean()


class GroupSubscriberRemove(GroupAssociationMixin, Mutation):
    class Arguments:
        data = GroupSubscribersInput(required=True)

    ok = Boolean()
