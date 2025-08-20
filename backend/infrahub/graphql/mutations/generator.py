from __future__ import annotations

from typing import TYPE_CHECKING

from graphene import Boolean, Field, InputField, InputObjectType, List, Mutation, NonNull, String

from infrahub.core.manager import NodeManager
from infrahub.generators.models import ProposedChangeGeneratorDefinition, RequestGeneratorDefinitionRun
from infrahub.graphql.context import apply_external_context
from infrahub.graphql.types.context import ContextInput
from infrahub.graphql.types.task import TaskInfo
from infrahub.workflows.catalogue import REQUEST_GENERATOR_DEFINITION_RUN

if TYPE_CHECKING:
    from graphql import GraphQLResolveInfo

    from ..initialization import GraphqlContext


class GeneratorDefinitionRequestRunInput(InputObjectType):
    id = InputField(String(required=True), description="ID of the generator definition to run")
    nodes = InputField(List(of_type=NonNull(String)), description="ID list of targets to run the generator for")


class GeneratorDefinitionRequestRun(Mutation):
    class Arguments:
        data = GeneratorDefinitionRequestRunInput(required=True)
        context = ContextInput(required=False)
        wait_until_completion = Boolean(required=False)

    ok = Boolean()
    task = Field(TaskInfo, required=False)

    @classmethod
    async def mutate(
        cls,
        root: dict,  # noqa: ARG003
        info: GraphQLResolveInfo,
        data: GeneratorDefinitionRequestRunInput,
        context: ContextInput | None = None,
        wait_until_completion: bool = True,
    ) -> GeneratorDefinitionRequestRun:
        graphql_context: GraphqlContext = info.context
        db = graphql_context.db
        await apply_external_context(graphql_context=graphql_context, context_input=context)
        generator_definition = await NodeManager.get_one(
            id=str(data.id), db=db, branch=graphql_context.branch, prefetch_relationships=True, raise_on_error=True
        )
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
            target_members=data.get("nodes", []),
        )

        if not wait_until_completion:
            workflow = await graphql_context.active_service.workflow.submit_workflow(
                workflow=REQUEST_GENERATOR_DEFINITION_RUN,
                context=graphql_context.get_context(),
                parameters={"model": request_model},
            )
            return cls(ok=True, task={"id": workflow.id})

        await graphql_context.active_service.workflow.execute_workflow(
            workflow=REQUEST_GENERATOR_DEFINITION_RUN,
            context=graphql_context.get_context(),
            parameters={"model": request_model},
        )
        return cls(ok=True)
