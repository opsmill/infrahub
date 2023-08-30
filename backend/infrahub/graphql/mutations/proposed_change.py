from typing import TYPE_CHECKING, Any, Dict, Optional

from graphene import Boolean, Enum, InputObjectType, Mutation, String
from graphql import GraphQLResolveInfo

from infrahub.core.manager import NodeManager
from infrahub.core.schema import NodeSchema
from infrahub.graphql.mutations.main import InfrahubMutationMixin
from infrahub.message_bus import messages

from .main import InfrahubMutationOptions

if TYPE_CHECKING:
    from neo4j import AsyncSession

    from infrahub.message_bus.rpc import InfrahubRpcClient


class CheckType(Enum):
    DATA = "data"
    REPOSITORY = "repository"
    SCHEMA = "schema"
    ALL = "all"


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
        rpc_client: InfrahubRpcClient = info.context.get("infrahub_rpc_client")

        proposed_change, result = await super().mutate_create(root=root, info=info, data=data, branch=branch, at=at)

        events = [
            messages.RequestProposedChangeDataIntegrity(proposed_change=proposed_change.id),
            messages.RequestProposedChangeRepositoryChecks(proposed_change=proposed_change.id),
            messages.RequestProposedChangeSchemaIntegrity(proposed_change=proposed_change.id),
        ]
        for event in events:
            await rpc_client.send(event)

        return proposed_change, result


class ProposedChangeRequestRunCheckInput(InputObjectType):
    id = String(required=True)
    check_type = CheckType(required=True)


class ProposedChangeRequestRefreshArtifactsInput(InputObjectType):
    id = String(required=True)


class ProposedChangeRequestRefreshArtifacts(Mutation):
    class Arguments:
        data = ProposedChangeRequestRefreshArtifactsInput(required=True)

    ok = Boolean()

    @classmethod
    async def mutate(
        cls,
        root: dict,  # pylint: disable=unused-argument
        info: GraphQLResolveInfo,
        data: Dict[str, Any],
    ) -> Dict[str, bool]:
        session: AsyncSession = info.context.get("infrahub_session")
        rpc_client: InfrahubRpcClient = info.context.get("infrahub_rpc_client")

        identifier = data.get("id", "")
        proposed_change = await NodeManager.get_one_by_id_or_default_filter(
            id=identifier, schema_name="CoreProposedChange", session=session
        )
        await rpc_client.send(messages.RequestProposedChangeRefreshArtifacts(proposed_change=proposed_change.id))
        return {"ok": True}


class ProposedChangeRequestRunCheck(Mutation):
    class Arguments:
        data = ProposedChangeRequestRunCheckInput(required=True)

    ok = Boolean()

    @classmethod
    async def mutate(
        cls,
        root: dict,  # pylint: disable=unused-argument
        info: GraphQLResolveInfo,
        data: Dict[str, Any],
    ) -> Dict[str, bool]:
        session: AsyncSession = info.context.get("infrahub_session")
        rpc_client: InfrahubRpcClient = info.context.get("infrahub_rpc_client")

        check_type = data.get("check_type")

        identifier = data.get("id", "")
        proposed_change = await NodeManager.get_one_by_id_or_default_filter(
            id=identifier, schema_name="CoreProposedChange", session=session
        )
        if check_type == CheckType.DATA:
            await rpc_client.send(messages.RequestProposedChangeDataIntegrity(proposed_change=proposed_change.id))
        elif check_type == CheckType.REPOSITORY:
            await rpc_client.send(messages.RequestProposedChangeRepositoryChecks(proposed_change=proposed_change.id))
        elif check_type == CheckType.SCHEMA:
            await rpc_client.send(messages.RequestProposedChangeSchemaIntegrity(proposed_change=proposed_change.id))
        else:
            events = [
                messages.RequestProposedChangeDataIntegrity(proposed_change=proposed_change.id),
                messages.RequestProposedChangeRepositoryChecks(proposed_change=proposed_change.id),
                messages.RequestProposedChangeSchemaIntegrity(proposed_change=proposed_change.id),
                messages.RequestProposedChangeRefreshArtifacts(proposed_change=proposed_change.id),
            ]
            for event in events:
                await rpc_client.send(event)

        return {"ok": True}
