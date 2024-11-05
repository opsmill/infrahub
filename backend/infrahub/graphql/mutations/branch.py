from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pydantic
from graphene import Boolean, Field, InputField, InputObjectType, List, Mutation, ObjectType, String
from infrahub_sdk.utils import extract_fields, extract_fields_first_node
from opentelemetry import trace
from typing_extensions import Self

from infrahub import lock
from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.diff.branch_differ import BranchDiffer
from infrahub.core.diff.coordinator import DiffCoordinator
from infrahub.core.diff.merger.merger import DiffMerger
from infrahub.core.diff.repository.repository import DiffRepository
from infrahub.core.merge import BranchMerger
from infrahub.core.task import UserTask
from infrahub.core.validators.determiner import ConstraintValidatorDeterminer
from infrahub.core.validators.models.validate_migration import SchemaValidateMigrationData
from infrahub.core.validators.tasks import schema_validate_migrations
from infrahub.database import retry_db_transaction
from infrahub.dependencies.registry import get_component_registry
from infrahub.exceptions import BranchNotFoundError, ValidationError
from infrahub.log import get_log_data, get_logger
from infrahub.message_bus import Meta, messages
from infrahub.worker import WORKER_IDENTITY
from infrahub.workflows.catalogue import BRANCH_DELETE, BRANCH_MERGE, BRANCH_REBASE

from ..types import BranchType

if TYPE_CHECKING:
    from graphql import GraphQLResolveInfo

    from ..initialization import GraphqlContext


# pylint: disable=unused-argument

log = get_logger()


class TaskInfo(ObjectType):
    id = Field(String)


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

    ok = Boolean()
    messages = List(String)
    object = Field(BranchType)

    @classmethod
    @retry_db_transaction(name="branch_validate")
    async def mutate(cls, root: dict, info: GraphQLResolveInfo, data: BranchNameInput) -> Self:
        context: GraphqlContext = info.context

        async with UserTask.from_graphql_context(title=f"Validate branch: {data['name']}", context=context):
            obj = await Branch.get_by_name(db=context.db, name=data["name"])
            ok = True
            validation_messages = ""

            diff = await BranchDiffer.init(db=context.db, branch=obj)
            conflicts = await diff.get_conflicts()

            if conflicts:
                ok = False
                errors = [str(conflict) for conflict in conflicts]
                validation_messages = ", ".join(errors)

            fields = await extract_fields(info.field_nodes[0].selection_set)

            return cls(
                object=await obj.to_graphql(fields=fields.get("object", {})), messages=validation_messages, ok=ok
            )


class BranchMerge(Mutation):
    class Arguments:
        data = BranchNameInput(required=True)

    ok = Boolean()
    object = Field(BranchType)

    @classmethod
    async def mutate(cls, root: dict, info: GraphQLResolveInfo, data: BranchNameInput) -> Self:
        context: GraphqlContext = info.context

        if not context.service:
            raise ValueError("Service must be provided to merge a branch.")

        obj = await Branch.get_by_name(db=context.db, name=data["name"])
        base_branch = await Branch.get_by_name(db=context.db, name=registry.default_branch)

        component_registry = get_component_registry()
        diff_coordinator = await component_registry.get_component(DiffCoordinator, db=context.db, branch=obj)
        diff_repository = await component_registry.get_component(DiffRepository, db=context.db, branch=obj)
        diff_merger = await component_registry.get_component(DiffMerger, db=context.db, branch=obj)
        enriched_diff = await diff_coordinator.update_branch_diff(base_branch=base_branch, diff_branch=obj)
        if enriched_diff.get_all_conflicts():
            raise ValidationError(
                f"Branch {obj.name} contains conflicts with the default branch."
                " Please create a Proposed Change to resolve the conflicts or manually update them before merging."
            )
        node_diff_field_summaries = await diff_repository.get_node_field_summaries(
            diff_branch_name=enriched_diff.diff_branch_name, diff_id=enriched_diff.uuid
        )

        merger = BranchMerger(
            db=context.db,
            diff_coordinator=diff_coordinator,
            diff_merger=diff_merger,
            source_branch=obj,
            service=context.service,
        )
        candidate_schema = merger.get_candidate_schema()
        determiner = ConstraintValidatorDeterminer(schema_branch=candidate_schema)
        constraints = await determiner.get_constraints(node_diffs=node_diff_field_summaries)
        if obj.has_schema_changes:
            constraints += await merger.calculate_validations(target_schema=candidate_schema)

        if constraints:
            error_messages = await schema_validate_migrations(
                message=SchemaValidateMigrationData(branch=obj, schema_branch=candidate_schema, constraints=constraints)
            )
            if error_messages:
                raise ValidationError(",\n".join(error_messages))

        await context.service.workflow.execute_workflow(workflow=BRANCH_MERGE, parameters={"branch": obj.name})

        # Pull the latest information about the branch from the database directly
        obj = await Branch.get_by_name(db=context.db, name=data["name"])

        fields = await extract_fields(info.field_nodes[0].selection_set)
        ok = True

        return cls(object=await obj.to_graphql(fields=fields.get("object", {})), ok=ok)
