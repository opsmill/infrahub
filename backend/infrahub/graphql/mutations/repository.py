from __future__ import annotations

from typing import TYPE_CHECKING

from graphene import InputObjectType, Mutation

from infrahub.core.schema import NodeSchema
from infrahub.log import get_logger
from infrahub.message_bus import messages

from .main import InfrahubMutationMixin, InfrahubMutationOptions

if TYPE_CHECKING:
    from graphql import GraphQLResolveInfo

    from infrahub.core.branch import Branch
    from infrahub.message_bus.rpc import InfrahubRpcClient

log = get_logger()


class InfrahubRepositoryMutation(InfrahubMutationMixin, Mutation):
    @classmethod
    def __init_subclass_with_meta__(cls, schema: NodeSchema = None, _meta=None, **options):  # pylint: disable=arguments-differ
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
        branch: Branch,
        at: str,
    ):
        obj, result = await super().mutate_create(root, info, data, branch, at)

        # Create the new repository in the filesystem.
        rpc_client: InfrahubRpcClient = info.context.get("infrahub_rpc_client")
        log.info("create_repository", name=obj.name.value)
        message = messages.GitRepositoryAdd(
            repository_id=obj.id, repository_name=obj.name.value, location=obj.location.value
        )
        await rpc_client.send(message=message)

        # TODO Validate that the creation of the repository went as expected

        return obj, result
