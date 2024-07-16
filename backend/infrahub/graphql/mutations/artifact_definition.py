from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional

from graphene import InputObjectType, Mutation
from typing_extensions import Self

from infrahub.core.schema import NodeSchema
from infrahub.log import get_logger
from infrahub.message_bus import messages

from .main import InfrahubMutationMixin, InfrahubMutationOptions

if TYPE_CHECKING:
    from graphql import GraphQLResolveInfo

    from infrahub.core.branch import Branch
    from infrahub.core.node import Node
    from infrahub.database import InfrahubDatabase
    from infrahub.graphql import GraphqlContext

log = get_logger()


class InfrahubArtifactDefinitionMutation(InfrahubMutationMixin, Mutation):
    @classmethod
    def __init_subclass_with_meta__(  # pylint: disable=arguments-differ
        cls,
        schema: NodeSchema,
        _meta: Optional[Any] = None,
        **options: dict[str, Any],
    ) -> None:
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
        database: Optional[InfrahubDatabase] = None,
    ) -> tuple[Node, Self]:
        context: GraphqlContext = info.context

        artifact_definition, result = await super().mutate_create(root=root, info=info, data=data, branch=branch, at=at)

        events = [
            messages.RequestArtifactDefinitionGenerate(artifact_definition=artifact_definition.id, branch=branch.name),
        ]

        if context.service:
            for event in events:
                await context.service.send(message=event)

        return artifact_definition, result

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
    ) -> tuple[Node, Self]:
        context: GraphqlContext = info.context

        artifact_definition, result = await super().mutate_update(root=root, info=info, data=data, branch=branch, at=at)

        events = [
            messages.RequestArtifactDefinitionGenerate(artifact_definition=artifact_definition.id, branch=branch.name),
        ]

        if context.service:
            for event in events:
                await context.service.send(message=event)

        return artifact_definition, result
