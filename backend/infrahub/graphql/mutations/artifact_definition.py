from __future__ import annotations

from typing import TYPE_CHECKING, Any

from graphene import InputObjectType, Mutation
from typing_extensions import Self

from infrahub.core.schema import NodeSchema
from infrahub.git.models import RequestArtifactDefinitionGenerate
from infrahub.log import get_logger
from infrahub.workflows.catalogue import REQUEST_ARTIFACT_DEFINITION_GENERATE

from .main import InfrahubMutationMixin, InfrahubMutationOptions

if TYPE_CHECKING:
    from graphql import GraphQLResolveInfo

    from infrahub.core.branch import Branch
    from infrahub.core.node import Node
    from infrahub.database import InfrahubDatabase
    from infrahub.graphql.initialization import GraphqlContext

log = get_logger()


class InfrahubArtifactDefinitionMutation(InfrahubMutationMixin, Mutation):
    @classmethod
    def __init_subclass_with_meta__(
        cls,
        schema: NodeSchema,
        _meta: Any | None = None,
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
        info: GraphQLResolveInfo,
        data: InputObjectType,
        branch: Branch,
        database: InfrahubDatabase | None = None,  # noqa: ARG003
    ) -> tuple[Node, Self]:
        graphql_context: GraphqlContext = info.context

        artifact_definition, result = await super().mutate_create(info=info, data=data, branch=branch)

        if graphql_context.service:
            model = RequestArtifactDefinitionGenerate(
                branch=branch.name,
                artifact_definition_id=artifact_definition.id,
                artifact_definition_name=artifact_definition.name.value,  # type: ignore[attr-defined]
            )
            await graphql_context.service.workflow.submit_workflow(
                workflow=REQUEST_ARTIFACT_DEFINITION_GENERATE,
                context=graphql_context.get_context(),
                parameters={"model": model},
            )

        return artifact_definition, result

    @classmethod
    async def mutate_update(
        cls,
        info: GraphQLResolveInfo,
        data: InputObjectType,
        branch: Branch,
        database: InfrahubDatabase | None = None,  # noqa: ARG003
        node: Node | None = None,  # noqa: ARG003
    ) -> tuple[Node, Self]:
        graphql_context: GraphqlContext = info.context

        artifact_definition, result = await super().mutate_update(info=info, data=data, branch=branch)

        if graphql_context.service:
            model = RequestArtifactDefinitionGenerate(
                branch=branch.name,
                artifact_definition_id=artifact_definition.id,
                artifact_definition_name=artifact_definition.name.value,  # type: ignore[attr-defined]
            )
            await graphql_context.service.workflow.submit_workflow(
                workflow=REQUEST_ARTIFACT_DEFINITION_GENERATE,
                context=graphql_context.get_context(),
                parameters={"model": model},
            )

        return artifact_definition, result
