from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from graphene import InputObjectType, Mutation

from infrahub.core.node import Node
from infrahub.core.schema import NodeSchema
from infrahub.log import get_logger
from infrahub.message_bus import messages

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
        db: InfrahubDatabase = info.context.get("infrahub_database")
        rpc_client: InfrahubRpcClient = info.context.get("infrahub_rpc_client")

        # Create the new repository in the database.
        obj = await Node.init(db=db, schema=cls._meta.schema, branch=branch, at=at)
        await obj.new(db=db, **data)
        await cls.validate_constraints(db=db, node=obj, branch=branch)
        async with db.start_transaction() as db:
            await obj.save(db=db)

        fields = await extract_fields(info.field_nodes[0].selection_set)

        # Create the new repository in the filesystem.
        log.info("create_repository", name=obj.name.value)
        message = messages.GitRepositoryAdd(
            repository_id=obj.id, repository_name=obj.name.value, location=obj.location.value
        )
        await rpc_client.send(message=message)

        # TODO Validate that the creation of the repository went as expected
        ok = True

        return obj, cls(object=await obj.to_graphql(db=db, fields=fields.get("object", {})), ok=ok)
