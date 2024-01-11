from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from graphene import InputObjectType, Mutation

from infrahub.core.manager import NodeManager
from infrahub.core.schema import NodeSchema
from infrahub.log import get_logger
from infrahub.message_bus import messages

from .main import InfrahubMutationMixin, InfrahubMutationOptions

if TYPE_CHECKING:
    from graphql import GraphQLResolveInfo

    from infrahub.core.branch import Branch
    from infrahub.core.node import Node
    from infrahub.database import InfrahubDatabase
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

        if obj.get_kind() == "CoreReadOnlyRepository":
            message = messages.GitRepositoryAddReadOnly(
                repository_id=obj.id,
                repository_name=obj.name.value,
                location=obj.location.value,
                ref=obj.ref.value,
                infrahub_branch_name=branch.name,
            )
        else:
            message = messages.GitRepositoryAdd(
                repository_id=obj.id,
                repository_name=obj.name.value,
                location=obj.location.value,
                default_branch_name=obj.default_branch.value,
            )
        await rpc_client.send(message=message)

        # TODO Validate that the creation of the repository went as expected

        return obj, result

    @classmethod
    async def mutate_update(
        cls,
        root: dict,
        info: GraphQLResolveInfo,
        data: InputObjectType,
        branch: Branch,
        at: str,
        database: Optional[InfrahubDatabase] = None,
        node: Optional[Node] = None,
    ):
        db: InfrahubDatabase = database or info.context.get("infrahub_database")
        rpc_client: InfrahubRpcClient = info.context.get("infrahub_rpc_client")
        if not node:
            node = await NodeManager.get_one_by_id_or_default_filter(
                db=db,
                schema_name=cls._meta.schema.kind,
                id=data.get("id"),
                branch=branch,
                at=at,
                include_owner=True,
                include_source=True,
            )
        current_commit = node.commit.value
        current_ref = node.ref.value
        new_commit = None
        if data.commit and data.commit.value:
            new_commit = data.commit.value
        new_ref = None
        if data.ref and data.ref.value:
            new_ref = data.ref.value

        obj, result = await super().mutate_update(root, info, data, branch, at, database=db, node=node)

        send_update_message = False

        if obj.get_kind() == "CoreReadOnlyRepository":
            if (new_commit and new_commit != current_commit) or (new_ref and new_ref != current_ref):
                send_update_message = True
        if not send_update_message:
            return obj, result

        log.info(
            "update read-only repository commit",
            name=obj.name.value,
            commit=data.commit.value if data.commit else None,
            ref=data.ref.value if data.ref else None,
        )

        message = messages.GitRepositoryPullReadOnly(
            repository_id=obj.id,
            repository_name=obj.name.value,
            location=obj.location.value,
            ref=obj.ref.value,
            commit=new_commit,
            infrahub_branch_name=branch.name,
        )

        await rpc_client.send(message=message)
        return obj, result
