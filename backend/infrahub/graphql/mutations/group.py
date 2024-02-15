from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict

from graphene import Boolean, InputObjectType, List, Mutation, String

from infrahub.core.manager import NodeManager
from infrahub.exceptions import NodeNotFound

if TYPE_CHECKING:
    from graphql import GraphQLResolveInfo

    from infrahub.graphql import GraphqlContext


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
        data: Dict[str, Any],
    ) -> None:
        context: GraphqlContext = info.context

        if not (
            group := await NodeManager.get_one(
                db=context.db,
                id=str(data.get("id")),
                branch=context.branch,
                at=context.at,
                include_owner=True,
                include_source=True,
            )
        ):
            raise NodeNotFound(branch_name=context.branch.name, node_type="Group", identifier=str(data.get("id")))

        if cls.__name__ == "GroupMemberAdd":
            await group.members.add(db=context.db, nodes=data["members"])  # type: ignore[attr-defined]
        elif cls.__name__ == "GroupMemberRemove":
            await group.members.remove(db=context.db, nodes=data["members"])  # type: ignore[attr-defined]
        elif cls.__name__ == "GroupSubscriberAdd":
            await group.subscribers.add(db=context.db, nodes=data["subscribers"])  # type: ignore[attr-defined]
        elif cls.__name__ == "GroupSubscriberRemove":
            await group.subscribers.remove(db=context.db, nodes=data["subscribers"])  # type: ignore[attr-defined]


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
