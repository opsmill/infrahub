from __future__ import annotations

from typing import TYPE_CHECKING, Optional

import pydantic
from graphene import Boolean, Field, InputObjectType, List, Mutation, String
from infrahub_sdk.utils import extract_fields, extract_fields_first_node
from typing_extensions import Self

from infrahub import config, lock
from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.diff.branch_differ import BranchDiffer
from infrahub.core.merge import BranchMerger
from infrahub.core.migrations.schema.runner import schema_migrations_runner
from infrahub.core.task import UserTask
from infrahub.core.validators.checker import schema_validators_checker
from infrahub.database import retry_db_transaction
from infrahub.exceptions import BranchNotFoundError, ValidationError
from infrahub.log import get_log_data, get_logger
from infrahub.message_bus import Meta, messages
from infrahub.services import services
from infrahub.worker import WORKER_IDENTITY

from ..types import BranchType

if TYPE_CHECKING:
    from graphql import GraphQLResolveInfo

    from .. import GraphqlContext


# pylint: disable=unused-argument

log = get_logger()


class BranchCreateInput(InputObjectType):
    id = String(required=False)
    name = String(required=True)
    description = String(required=False)
    origin_branch = String(required=False)
    branched_from = String(required=False)
    sync_with_git = Boolean(required=False)
    is_isolated = Boolean(required=False)


class BranchCreate(Mutation):
    class Arguments:
        data = BranchCreateInput(required=True)
        background_execution = Boolean(required=False)

    ok = Boolean()
    object = Field(BranchType)

    @classmethod
    @retry_db_transaction(name="branch_create")
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

            try:
                obj = Branch(**data)
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
    is_isolated = Boolean(required=False)


class BranchDelete(Mutation):
    class Arguments:
        data = BranchNameInput(required=True)

    ok = Boolean()

    @classmethod
    @retry_db_transaction(name="branch_delete")
    async def mutate(cls, root: dict, info: GraphQLResolveInfo, data: BranchNameInput) -> Self:
        context: GraphqlContext = info.context

        async with UserTask.from_graphql_context(title=f"Delete branch: {data['name']}", context=context):
            obj = await Branch.get_by_name(db=context.db, name=str(data.name))
            await obj.delete(db=context.db)

            if context.service:
                log_data = get_log_data()
                request_id = log_data.get("request_id", "")
                message = messages.EventBranchDelete(
                    branch=obj.name,
                    branch_id=str(obj.id),
                    sync_with_git=obj.sync_with_git,
                    meta=Meta(request_id=request_id),
                )
                await context.service.send(message=message)

            return cls(ok=True)


class BranchUpdate(Mutation):
    class Arguments:
        data = BranchUpdateInput(required=True)

    ok = Boolean()

    @classmethod
    @retry_db_transaction(name="branch_update")
    async def mutate(cls, root: dict, info: GraphQLResolveInfo, data: BranchNameInput) -> Self:
        context: GraphqlContext = info.context

        obj = await Branch.get_by_name(db=context.db, name=data["name"])

        if (
            obj.is_isolated is True
            and "is_isolated" in data
            and data["is_isolated"] is False
            and obj.has_schema_changes
        ):
            raise ValueError(
                f"Unsupported: Can't convert {obj.name} to non-isolated mode because it currently has some schema changes."
            )

        to_extract = ["description", "is_isolated"]
        for field_name in to_extract:
            if field_name in data and data.get(field_name) is not None:
                setattr(obj, field_name, data[field_name])

        async with context.db.start_transaction() as db:
            await obj.save(db=db)

        return cls(ok=True)


class BranchRebase(Mutation):
    class Arguments:
        data = BranchNameInput(required=True)

    ok = Boolean()
    object = Field(BranchType)

    @classmethod
    @retry_db_transaction(name="branch_rebase")
    async def mutate(cls, root: dict, info: GraphQLResolveInfo, data: BranchNameInput) -> Self:
        context: GraphqlContext = info.context

        if not context.service:
            raise ValueError("Service must be provided to rebase a branch.")

        async with UserTask.from_graphql_context(title=f"Rebase branch : {data.name}", context=context) as task:
            obj = await Branch.get_by_name(db=context.db, name=str(data.name))
            merger = BranchMerger(db=context.db, source_branch=obj, service=context.service)

            # If there are some changes related to the schema between this branch and main, we need to
            #  - Run all the validations to ensure everything if correct before rebasing the branch
            #  - Run all the migrations after the rebase
            if obj.has_schema_changes:
                candidate_schema = merger.get_candidate_schema()
                constraints = await merger.calculate_validations(target_schema=candidate_schema)
                error_messages, _ = await schema_validators_checker(
                    branch=obj, schema=candidate_schema, constraints=constraints, service=context.service
                )
                if error_messages:
                    raise ValidationError(",\n".join(error_messages))

            schema_in_main_before = merger.destination_schema.duplicate()

            async with context.db.start_transaction() as dbt:
                await obj.rebase(db=dbt)
                await task.info(message="Branch successfully rebased", db=dbt)

            if obj.has_schema_changes:
                schema_diff = await merger.get_schema_diff()
                updated_schema = await registry.schema.load_schema_from_db(
                    db=context.db,
                    branch=obj,
                    schema=merger.source_schema.duplicate(),
                    schema_diff=schema_diff,
                )
                registry.schema.set_schema_branch(name=obj.name, schema=updated_schema)
                obj.update_schema_hash()
                await obj.save(db=context.db)

                # Execute the migrations
                migrations = await merger.calculate_migrations(target_schema=updated_schema)

                errors = await schema_migrations_runner(
                    branch=merger.source_branch,
                    new_schema=candidate_schema,
                    previous_schema=schema_in_main_before,
                    migrations=migrations,
                    service=context.service,
                )
                for error in errors:
                    context.service.log.error(error)

            fields = await extract_fields_first_node(info=info)

            ok = True

            if context.service:
                log_data = get_log_data()
                request_id = log_data.get("request_id", "")
                message = messages.EventBranchRebased(
                    branch=obj.name,
                    meta=Meta(initiator_id=WORKER_IDENTITY, request_id=request_id),
                )
                await context.service.send(message=message)

            return cls(object=await obj.to_graphql(fields=fields.get("object", {})), ok=ok)


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
    @retry_db_transaction(name="branch_merge")
    async def mutate(cls, root: dict, info: GraphQLResolveInfo, data: BranchNameInput) -> Self:
        context: GraphqlContext = info.context

        async with UserTask.from_graphql_context(title=f"Merge branch: {data['name']}", context=context) as task:
            obj = await Branch.get_by_name(db=context.db, name=data["name"])

            merger: Optional[BranchMerger] = None
            async with lock.registry.global_graph_lock():
                async with context.db.start_transaction() as db:
                    merger = BranchMerger(db=db, source_branch=obj, service=context.service)
                    await merger.merge()
                    await merger.update_schema()

            fields = await extract_fields(info.field_nodes[0].selection_set)

            ok = True

            if merger and merger.migrations and context.service:
                errors = await schema_migrations_runner(
                    branch=merger.destination_branch,
                    new_schema=merger.destination_schema,
                    previous_schema=merger.initial_source_schema,
                    migrations=merger.migrations,
                    service=context.service,
                )
                for error in errors:
                    await task.error(message=error)

            if config.SETTINGS.broker.enable and context.background:
                log_data = get_log_data()
                request_id = log_data.get("request_id", "")
                message = messages.EventBranchMerge(
                    source_branch=obj.name,
                    target_branch=registry.default_branch,
                    meta=Meta(initiator_id=WORKER_IDENTITY, request_id=request_id),
                )
                context.background.add_task(services.send, message)

            return cls(object=await obj.to_graphql(fields=fields.get("object", {})), ok=ok)
