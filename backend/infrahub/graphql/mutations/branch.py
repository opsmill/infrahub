from __future__ import annotations

from typing import TYPE_CHECKING

from graphene import Boolean, Field, InputField, InputObjectType, Mutation, String
from infrahub_sdk.utils import extract_fields, extract_fields_first_node
from opentelemetry import trace
from typing_extensions import Self

from infrahub.core.branch import Branch
from infrahub.database import retry_db_transaction
from infrahub.graphql.context import apply_external_context
from infrahub.graphql.types.context import ContextInput
from infrahub.log import get_logger
from infrahub.workflows.catalogue import (
    BRANCH_CREATE,
    BRANCH_DELETE,
    BRANCH_MERGE_MUTATION,
    BRANCH_REBASE,
    BRANCH_VALIDATE,
)

from ..types import BranchType
from ..types.task import TaskInfo
from .models import BranchCreateModel

if TYPE_CHECKING:
    from graphql import GraphQLResolveInfo

    from ..initialization import GraphqlContext


log = get_logger()


class BranchCreateInput(InputObjectType):
    id = String(required=False)
    name = String(required=True)
    description = String(required=False)
    origin_branch = String(required=False)
    branched_from = String(required=False)
    sync_with_git = Boolean(required=False)
    is_isolated = InputField(Boolean(required=False), deprecation_reason="Non isolated mode is not supported anymore")


class BranchCreate(Mutation):
    class Arguments:
        data = BranchCreateInput(required=True)
        context = ContextInput(required=False)
        background_execution = Boolean(required=False, deprecation_reason="Please use `wait_until_completion` instead")
        wait_until_completion = Boolean(required=False)

    ok = Boolean()
    object = Field(BranchType)
    task = Field(TaskInfo, required=False)

    @classmethod
    @trace.get_tracer(__name__).start_as_current_span("branch_create")
    async def mutate(
        cls,
        root: dict,  # noqa: ARG003
        info: GraphQLResolveInfo,
        data: BranchCreateInput,
        context: ContextInput | None = None,
        background_execution: bool = False,
        wait_until_completion: bool = True,
    ) -> Self:
        graphql_context: GraphqlContext = info.context
        task: dict | None = None

        model = BranchCreateModel(**data)
        await apply_external_context(graphql_context=graphql_context, context_input=context)

        if background_execution or not wait_until_completion:
            workflow = await graphql_context.active_service.workflow.submit_workflow(
                workflow=BRANCH_CREATE, context=graphql_context.get_context(), parameters={"model": model}
            )
            task = {"id": workflow.id}
            return cls(ok=True, task=task)

        await graphql_context.active_service.workflow.execute_workflow(
            workflow=BRANCH_CREATE, context=graphql_context.get_context(), parameters={"model": model}
        )

        # Retrieve created branch
        obj = await Branch.get_by_name(db=graphql_context.db, name=model.name)
        fields = await extract_fields(info.field_nodes[0].selection_set)
        return cls(object=await obj.to_graphql(fields=fields.get("object", {})), ok=True, task=task)


class BranchNameInput(InputObjectType):
    name = String(required=False)


class BranchUpdateInput(InputObjectType):
    name = String(required=True)
    description = String(required=False)
    is_isolated = InputField(Boolean(required=False), deprecation_reason="Non isolated mode is not supported anymore")


class BranchDelete(Mutation):
    class Arguments:
        data = BranchNameInput(required=True)
        context = ContextInput(required=False)
        wait_until_completion = Boolean(required=False)

    ok = Boolean()
    task = Field(TaskInfo, required=False)

    @classmethod
    async def mutate(
        cls,
        root: dict,  # noqa: ARG003
        info: GraphQLResolveInfo,
        data: BranchNameInput,
        context: ContextInput | None = None,
        wait_until_completion: bool = True,
    ) -> Self:
        graphql_context: GraphqlContext = info.context
        obj = await Branch.get_by_name(db=graphql_context.db, name=str(data.name))
        await apply_external_context(graphql_context=graphql_context, context_input=context)

        if wait_until_completion:
            await graphql_context.active_service.workflow.execute_workflow(
                workflow=BRANCH_DELETE, context=graphql_context.get_context(), parameters={"branch": obj.name}
            )
            return cls(ok=True)

        workflow = await graphql_context.active_service.workflow.submit_workflow(
            workflow=BRANCH_DELETE, context=graphql_context.get_context(), parameters={"branch": obj.name}
        )
        return cls(ok=True, task={"id": str(workflow.id)})


class BranchUpdate(Mutation):
    class Arguments:
        data = BranchUpdateInput(required=True)
        context = ContextInput(required=False)

    ok = Boolean()

    @classmethod
    @retry_db_transaction(name="branch_update")
    async def mutate(
        cls,
        root: dict,  # noqa: ARG003
        info: GraphQLResolveInfo,
        data: BranchNameInput,
        context: ContextInput | None = None,
    ) -> Self:
        graphql_context: GraphqlContext = info.context

        obj = await Branch.get_by_name(db=graphql_context.db, name=data["name"])
        await apply_external_context(graphql_context=graphql_context, context_input=context)

        to_extract = ["description"]
        for field_name in to_extract:
            if field_name in data and data.get(field_name) is not None:
                setattr(obj, field_name, data[field_name])

        async with graphql_context.db.start_transaction() as db:
            await obj.save(db=db)

        return cls(ok=True)


class BranchRebase(Mutation):
    class Arguments:
        data = BranchNameInput(required=True)
        context = ContextInput(required=False)
        wait_until_completion = Boolean(required=False)

    ok = Boolean()
    object = Field(BranchType)
    task = Field(TaskInfo, required=False)

    @classmethod
    async def mutate(
        cls,
        root: dict,  # noqa: ARG003
        info: GraphQLResolveInfo,
        data: BranchNameInput,
        context: ContextInput | None = None,
        wait_until_completion: bool = True,
    ) -> Self:
        graphql_context: GraphqlContext = info.context

        obj = await Branch.get_by_name(db=graphql_context.db, name=str(data.name))
        await apply_external_context(graphql_context=graphql_context, context_input=context)
        task: dict | None = None

        if wait_until_completion:
            await graphql_context.active_service.workflow.execute_workflow(
                workflow=BRANCH_REBASE, context=graphql_context.get_context(), parameters={"branch": obj.name}
            )

            # Pull the latest information about the branch from the database directly
            obj = await Branch.get_by_name(db=graphql_context.db, name=str(data.name))
        else:
            workflow = await graphql_context.active_service.workflow.submit_workflow(
                workflow=BRANCH_REBASE, context=graphql_context.get_context(), parameters={"branch": obj.name}
            )
            task = {"id": workflow.id}

        fields = await extract_fields_first_node(info=info)
        ok = True

        return cls(object=await obj.to_graphql(fields=fields.get("object", {})), ok=ok, task=task)


class BranchValidate(Mutation):
    class Arguments:
        data = BranchNameInput(required=True)
        context = ContextInput(required=False)
        wait_until_completion = Boolean(required=False)

    ok = Boolean()
    object = Field(BranchType)
    task = Field(TaskInfo, required=False)

    @classmethod
    @retry_db_transaction(name="branch_validate")
    async def mutate(
        cls,
        root: dict,  # noqa: ARG003
        info: GraphQLResolveInfo,
        data: BranchNameInput,
        context: ContextInput | None = None,
        wait_until_completion: bool = True,
    ) -> Self:
        graphql_context: GraphqlContext = info.context

        obj = await Branch.get_by_name(db=graphql_context.db, name=str(data.name))
        await apply_external_context(graphql_context=graphql_context, context_input=context)
        task: dict | None = None
        ok = True

        if wait_until_completion:
            await graphql_context.active_service.workflow.execute_workflow(
                workflow=BRANCH_VALIDATE, context=graphql_context.get_context(), parameters={"branch": obj.name}
            )
        else:
            workflow = await graphql_context.active_service.workflow.submit_workflow(
                workflow=BRANCH_VALIDATE, context=graphql_context.get_context(), parameters={"branch": obj.name}
            )
            task = {"id": workflow.id}

        fields = await extract_fields_first_node(info=info)

        return cls(object=await obj.to_graphql(fields=fields.get("object", {})), ok=ok, task=task)


class BranchMerge(Mutation):
    class Arguments:
        data = BranchNameInput(required=True)
        context = ContextInput(required=False)
        wait_until_completion = Boolean(required=False)

    ok = Boolean()
    object = Field(BranchType)
    task = Field(TaskInfo, required=False)

    @classmethod
    async def mutate(
        cls,
        root: dict,  # noqa: ARG003
        info: GraphQLResolveInfo,
        data: BranchNameInput,
        context: ContextInput | None = None,
        wait_until_completion: bool = True,
    ) -> Self:
        branch_name = data["name"]
        task: dict | None = None
        graphql_context: GraphqlContext = info.context
        await apply_external_context(graphql_context=graphql_context, context_input=context)

        if wait_until_completion:
            await graphql_context.active_service.workflow.execute_workflow(
                workflow=BRANCH_MERGE_MUTATION,
                context=graphql_context.get_context(),
                parameters={"branch": branch_name},
            )
        else:
            workflow = await graphql_context.active_service.workflow.submit_workflow(
                workflow=BRANCH_MERGE_MUTATION,
                context=graphql_context.get_context(),
                parameters={"branch": branch_name},
            )
            task = {"id": workflow.id}

        # Pull the latest information about the branch from the database directly
        obj = await Branch.get_by_name(db=graphql_context.db, name=branch_name)

        fields = await extract_fields(info.field_nodes[0].selection_set)
        ok = True

        return cls(object=await obj.to_graphql(fields=fields.get("object", {})), ok=ok, task=task)
