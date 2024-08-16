from typing import TYPE_CHECKING

from graphene import Boolean, DateTime, InputObjectType, Mutation, String
from graphql import GraphQLResolveInfo

from infrahub.message_bus import messages

if TYPE_CHECKING:
    from .. import GraphqlContext


class DiffUpdateInput(InputObjectType):
    branch = String(required=True)
    name = String(required=False)
    from_time = DateTime(required=False)
    to_time = DateTime(required=False)


class DiffUpdateMutation(Mutation):
    class Arguments:
        data = DiffUpdateInput(required=True)

    ok = Boolean()

    @classmethod
    async def mutate(
        cls,
        root: dict,  # pylint: disable=unused-argument
        info: GraphQLResolveInfo,
        data: DiffUpdateInput,
    ) -> dict[str, bool]:
        context: GraphqlContext = info.context

        message = messages.RequestDiffUpdate(
            branch_name=str(data.branch),
            name=data.name,
            from_time=data.from_time,
            to_time=data.to_time,
        )
        if context.service:
            await context.service.send(message=message)

        return {"ok": True}
