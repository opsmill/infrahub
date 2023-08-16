from typing import TYPE_CHECKING, Optional

from graphene import InputObjectType, Mutation
from graphql import GraphQLResolveInfo

from infrahub.core.node import Node
from infrahub.core.registry import registry
from infrahub.core.schema import NodeSchema
from infrahub.graphql.mutations.main import InfrahubMutationMixin

from .main import InfrahubMutationOptions

if TYPE_CHECKING:
    from neo4j import AsyncSession


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
        proposed_change, result = await super().mutate_create(root=root, info=info, data=data, branch=branch, at=at)
        session: AsyncSession = info.context.get("infrahub_session")
        # rpc_client: InfrahubRpcClient = info.context.get("infrahub_rpc_client")

        # Create the new repository in the database.
        source_branch = await registry.get_branch(session=session, branch=proposed_change.source_branch.value)
        diff = await source_branch.diff(session=session, branch_only=False)
        conflicts = await diff.get_conflicts_graph(session=session)
        obj = await Node.init(session=session, schema="InternalDataIntegrityValidator", branch=branch)
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

        return proposed_change, result
