from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pydantic
from graphene import Boolean, Field, InputField, InputObjectType, Mutation, String
from infrahub_sdk.utils import extract_fields, extract_fields_first_node
from opentelemetry import trace
from typing_extensions import Self

from infrahub import lock
from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.task import UserTask
from infrahub.database import retry_db_transaction
from infrahub.exceptions import BranchNotFoundError
from infrahub.log import get_log_data, get_logger
from infrahub.message_bus import Meta, messages
from infrahub.worker import WORKER_IDENTITY
from infrahub.workflows.catalogue import (
    BRANCH_DELETE,
    BRANCH_MERGE_MUTATION,
    BRANCH_REBASE,
    BRANCH_VALIDATE,
)

from ..types import BranchType
from ..types.task import TaskInfo

if TYPE_CHECKING:
    from graphql import GraphQLResolveInfo

    from ..initialization import GraphqlContext


# pylint: disable=unused-argument

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
        background_execution = Boolean(required=False)

    ok = Boolean()
    object = Field(BranchType)

    @classmethod
    @retry_db_transaction(name="branch_create")
    @trace.get_tracer(__name__).start_as_current_span("branch_create")
    async def mutate(
        cls, root: dict, info: GraphQLResolveInfo, data: BranchCreateInput, background_execution: bool = False
    ) -> Self:
        context: GraphqlContext = info.context

        async with UserTask.from_graphql_context(title=f"Create branch : {data['name']}", context=context) as task:
            # Check if the branch already exist
            try:
                await Branch.get_by_name(db=context.db, name=data["name"])
                raise ValueError(f"The branch {data['name']}, already exist")
            except BranchNotFoundError:
                pass

            data_dict: dict[str, Any] = dict(data)
            if "is_isolated" in data_dict:
                del data_dict["is_isolated"]

            try:
                obj = Branch(**data_dict)
            except pydantic.ValidationError as exc:
                error_msgs = [f"invalid field {error['loc'][0]}: {error['msg']}" for error in exc.errors()]
                raise ValueError("\n".join(error_msgs)) from exc

            async with lock.registry.local_schema_lock():
                # Copy the schema from the origin branch and set the hash and the schema_changed_at value
                origin_schema = registry.schema.get_schema_branch(name=obj.origin_branch)
                new_schema = origin_schema.duplicate(name=obj.name)
                registry.schema.set_schema_branch(name=obj.name, schema=new_schema)
                obj.update_schema_hash()
                await obj.save(db=context.db)

                # Add Branch to registry
                registry.branch[obj.name] = obj

            await task.info(message="created_branch", name=obj.name)

            log_data = get_log_data()
            request_id = log_data.get("request_id", "")

            ok = True

            fields = await extract_fields(info.field_nodes[0].selection_set)
            if context.service:
                message = messages.EventBranchCreate(
                    branch=obj.name,
                    branch_id=str(obj.id),
                    sync_with_git=obj.sync_with_git,
                    meta=Meta(initiator_id=WORKER_IDENTITY, request_id=request_id),
                )
                await context.service.send(message=message)

            return cls(object=await obj.to_graphql(fields=fields.get("object", {})), ok=ok)


class BranchNameInput(InputObjectType):
    name = String(required=False)


class BranchUpdateInput(InputObjectType):
    name = String(required=True)
    description = String(required=False)
    is_isolated = InputField(Boolean(required=False), deprecation_reason="Non isolated mode is not supported anymore")


class BranchDelete(Mutation):
    class Arguments:
        data = BranchNameInput(required=True)
        wait_until_completion = Boolean(required=False)

    ok = Boolean()
    task = Field(TaskInfo, required=False)

    @classmethod
    @retry_db_transaction(name="branch_delete")
    async def mutate(
        cls, root: dict, info: GraphQLResolveInfo, data: BranchNameInput, wait_until_completion: bool = True
    ) -> Self:
        context: GraphqlContext = info.context
        obj = await Branch.get_by_name(db=context.db, name=str(data.name))

        if wait_until_completion:
            await context.active_service.workflow.execute_workflow(
                workflow=BRANCH_DELETE, parameters={"branch": obj.name}
            )
            return cls(ok=True)

        workflow = await context.active_service.workflow.submit_workflow(
            workflow=BRANCH_DELETE, parameters={"branch": obj.name}
        )
        return cls(ok=True, task={"id": str(workflow.id)})


class BranchUpdate(Mutation):
    class Arguments:
        data = BranchUpdateInput(required=True)

    ok = Boolean()

    @classmethod
    @retry_db_transaction(name="branch_update")
    async def mutate(cls, root: dict, info: GraphQLResolveInfo, data: BranchNameInput) -> Self:
        context: GraphqlContext = info.context

        obj = await Branch.get_by_name(db=context.db, name=data["name"])

        to_extract = ["description"]
        for field_name in to_extract:
            if field_name in data and data.get(field_name) is not None:
                setattr(obj, field_name, data[field_name])

        async with context.db.start_transaction() as db:
            await obj.save(db=db)

        return cls(ok=True)


class BranchRebase(Mutation):
    class Arguments:
        data = BranchNameInput(required=True)
        wait_until_completion = Boolean(required=False)

    ok = Boolean()
    object = Field(BranchType)
    task = Field(TaskInfo, required=False)

    @classmethod
    async def mutate(
        cls, root: dict, info: GraphQLResolveInfo, data: BranchNameInput, wait_until_completion: bool = True
    ) -> Self:
        context: GraphqlContext = info.context

        obj = await Branch.get_by_name(db=context.db, name=str(data.name))
        task: dict | None = None

        if wait_until_completion:
            await context.active_service.workflow.execute_workflow(
                workflow=BRANCH_REBASE, parameters={"branch": obj.name}
            )

            # Pull the latest information about the branch from the database directly
            obj = await Branch.get_by_name(db=context.db, name=str(data.name))
        else:
            workflow = await context.active_service.workflow.submit_workflow(
                workflow=BRANCH_REBASE, parameters={"branch": obj.name}
            )
            task = {"id": workflow.id}

        fields = await extract_fields_first_node(info=info)
        ok = True

        return cls(object=await obj.to_graphql(fields=fields.get("object", {})), ok=ok, task=task)


class BranchValidate(Mutation):
    class Arguments:
        data = BranchNameInput(required=True)
        wait_until_completion = Boolean(required=False)

    ok = Boolean()
    object = Field(BranchType)
    task = Field(TaskInfo, required=False)

    @classmethod
    @retry_db_transaction(name="branch_validate")
    async def mutate(
        cls, root: dict, info: GraphQLResolveInfo, data: BranchNameInput, wait_until_completion: bool = True
    ) -> Self:
        context: GraphqlContext = info.context

        obj = await Branch.get_by_name(db=context.db, name=str(data.name))
        task: dict | None = None
        ok = True

        if wait_until_completion:
            await context.active_service.workflow.execute_workflow(
                workflow=BRANCH_VALIDATE, parameters={"branch": obj.name}
            )
        else:
            workflow = await context.active_service.workflow.submit_workflow(
                workflow=BRANCH_VALIDATE, parameters={"branch": obj.name}
            )
            task = {"id": workflow.id}

        fields = await extract_fields_first_node(info=info)

        return cls(object=await obj.to_graphql(fields=fields.get("object", {})), ok=ok, task=task)


class BranchMerge(Mutation):
    class Arguments:
        data = BranchNameInput(required=True)
        wait_until_completion = Boolean(required=False)

    ok = Boolean()
    object = Field(BranchType)
    task = Field(TaskInfo, required=False)

    @classmethod
    async def mutate(
        cls, root: dict, info: GraphQLResolveInfo, data: BranchNameInput, wait_until_completion: bool = True
    ) -> Self:
        branch_name = data["name"]
        task: dict | None = None

        if wait_until_completion:
            await info.context.active_service.workflow.execute_workflow(
                workflow=BRANCH_MERGE_MUTATION, parameters={"branch": branch_name}
            )
        else:
            workflow = await info.context.active_service.workflow.submit_workflow(
                workflow=BRANCH_MERGE_MUTATION, parameters={"branch": branch_name}
            )
            task = {"id": workflow.id}

        # Pull the latest information about the branch from the database directly
        obj = await Branch.get_by_name(db=info.context.db, name=branch_name)

        fields = await extract_fields(info.field_nodes[0].selection_set)
        ok = True

        return cls(object=await obj.to_graphql(fields=fields.get("object", {})), ok=ok, task=task)
