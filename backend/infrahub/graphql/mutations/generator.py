from __future__ import annotations

from typing import TYPE_CHECKING, Any

from graphene import Boolean, InputObjectType, Mutation, String

from infrahub.core.manager import NodeManager
from infrahub.generators.models import ProposedChangeGeneratorDefinition, RequestGeneratorDefinitionRun
from infrahub.workflows.catalogue import REQUEST_GENERATOR_DEFINITION_RUN

if TYPE_CHECKING:
    from graphql import GraphQLResolveInfo

    from ..initialization import GraphqlContext


class GeneratorDefinitionRequestRunInput(InputObjectType):
    id = String(required=True)


class GeneratorDefinitionRequestRun(Mutation):
    class Arguments:
        data = GeneratorDefinitionRequestRunInput(required=True)

    ok = Boolean()

    @classmethod
    async def mutate(
        cls,
        root: dict,  # noqa: ARG003
        info: GraphQLResolveInfo,
        data: dict[str, Any],
    ) -> dict[str, bool]:
        graphql_context: GraphqlContext = info.context
        db = graphql_context.db

        generator_definition = await NodeManager.get_one(id=data.get("id", ""), db=db, prefetch_relationships=True)
        query = await generator_definition.query.get_peer(db=db)
        repository = await generator_definition.repository.get_peer(db=db)
        group = await generator_definition.targets.get_peer(db=db)

        request_model = RequestGeneratorDefinitionRun(
            generator_definition=ProposedChangeGeneratorDefinition(
                definition_id=generator_definition.id,
                definition_name=generator_definition.name.value,
                class_name=generator_definition.class_name.value,
                file_path=generator_definition.file_path.value,
                query_name=query.name.value,
                query_models=query.models.value,
                repository_id=repository.id,
                parameters=generator_definition.parameters.value,
                group_id=group.id,
                convert_query_response=generator_definition.convert_query_response.value or False,
            ),
            branch=graphql_context.branch.name,
        )
        if graphql_context.service:
            await graphql_context.service.workflow.submit_workflow(
                workflow=REQUEST_GENERATOR_DEFINITION_RUN,
                context=graphql_context.get_context(),
                parameters={"model": request_model},
            )

        return {"ok": True}
