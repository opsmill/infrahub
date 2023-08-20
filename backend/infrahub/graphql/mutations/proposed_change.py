from typing import TYPE_CHECKING, Dict, Optional

from graphene import Boolean, InputObjectType, Mutation, String
from graphql import GraphQLResolveInfo
from neo4j import AsyncSession

from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.registry import registry
from infrahub.core.schema import NodeSchema
from infrahub.exceptions import NodeNotFound
from infrahub.graphql.mutations.main import InfrahubMutationMixin
from infrahub.message_bus import messages

from .main import InfrahubMutationOptions

if TYPE_CHECKING:
    from infrahub.message_bus.rpc import InfrahubRpcClient


async def create_data_check(session: AsyncSession, proposed_change: Node) -> None:
    source_branch = await registry.get_branch(session=session, branch=proposed_change.source_branch.value)
    diff = await source_branch.diff(session=session, branch_only=False)
    conflicts = await diff.get_conflicts_graph(session=session)
    obj = await Node.init(session=session, schema="InternalDataIntegrityValidator")
    conflict_paths = []
    status = "passed"
    for conflict in conflicts:
        conflict_paths.append("/".join(conflict))
        status = "failed"
    await obj.new(
        session=session,
        proposed_change=proposed_change.id,
        conflict_paths=conflict_paths,
        state="completed",
        status=status,
    )
    await obj.save(session=session)


class InfrahubProposedChangeMutation(InfrahubMutationMixin, Mutation):
    @classmethod
    def __init_subclass_with_meta__(
        cls, schema: NodeSchema = None, _meta=None, **options
    ):  # pylint: disable=arguments-differ
        # Make sure schema is a valid NodeSchema Node Class
        if not isinstance(schema, NodeSchema):
            raise ValueError(f"You need to pass a valid NodeSchema in '{cls.__name__}.Meta', received '{schema}'")

        if not _meta:
            _meta = InfrahubMutationOptions(cls)
        _meta.schema = schema

        super().__init_subclass_with_meta__(_meta=_meta, **options)

    @classmethod
    async def mutate_create(
        cls,
        root: dict,
        info: GraphQLResolveInfo,
        data: InputObjectType,
        branch: Optional[str] = None,
        at: Optional[str] = None,
    ):
        session: AsyncSession = info.context.get("infrahub_session")
        rpc_client: InfrahubRpcClient = info.context.get("infrahub_rpc_client")

        proposed_change, result = await super().mutate_create(root=root, info=info, data=data, branch=branch, at=at)

        await create_data_check(session=session, proposed_change=proposed_change)

        await rpc_client.send(messages.RequestProposedChangeRepositoryChecks(proposed_change=proposed_change.id))

        return proposed_change, result


class ProposedChangeRequestRunCheckInput(InputObjectType):
    id = String(required=True)
    check_type = String(required=True)


class ProposedChangeRequestRunCheck(Mutation):
    class Arguments:
        data = ProposedChangeRequestRunCheckInput(required=True)

    ok = Boolean()

    @classmethod
    async def mutate(
        cls,
        root: dict,  # pylint: disable=unused-argument
        info: GraphQLResolveInfo,
        data: Dict[str, str],
    ) -> Dict[str, bool]:
        session: AsyncSession = info.context.get("infrahub_session")

        check_type = data.get("check_type")
        if check_type != "data":
            raise ValueError("Only 'data' check_type currently supported")

        identifier = data.get("id", "")
        proposed_change = await NodeManager.get_one(id=identifier, session=session)
        if not proposed_change:
            raise NodeNotFound(
                branch_name="-global-",
                node_type="CoreProposedChange",
                identifier=identifier,
                message="The requested proposed change wasn't found",
            )
        await create_data_check(session=session, proposed_change=proposed_change)

        return {"ok": True}
