from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from graphene import InputObjectType, Mutation

from infrahub.core.node import Node
from infrahub.core.schema import NodeSchema
from infrahub.log import get_log_data, get_logger
from infrahub.message_bus.events import GitMessageAction, InfrahubGitRPC

from ..utils import extract_fields
from .main import InfrahubMutationMixin, InfrahubMutationOptions

if TYPE_CHECKING:
    from graphql import GraphQLResolveInfo

    from infrahub.database import InfrahubDatabase
    from infrahub.message_bus.rpc import InfrahubRpcClient

log = get_logger()


class InfrahubRepositoryMutation(InfrahubMutationMixin, Mutation):
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
        db: InfrahubDatabase = info.context.get("infrahub_session")
        rpc_client: InfrahubRpcClient = info.context.get("infrahub_rpc_client")

        # Create the new repository in the database.
        obj = await Node.init(db=db, schema=cls._meta.schema, branch=branch, at=at)
        await obj.new(db=db, **data)
        await cls.validate_constraints(db=db, node=obj)
        await obj.save(db=db)

        fields = await extract_fields(info.field_nodes[0].selection_set)

        # Create the new repository in the filesystem.
        log.info("create_repository", name=obj.name.value)
        log_data = get_log_data()
        request_id = log_data.get("request_id", "")
        await rpc_client.call(InfrahubGitRPC(action=GitMessageAction.REPO_ADD, repository=obj, request_id=request_id))

        # TODO Validate that the creation of the repository went as expected
        ok = True

        return obj, cls(object=await obj.to_graphql(db=db, fields=fields.get("object", {})), ok=ok)
