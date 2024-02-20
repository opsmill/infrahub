from typing import TYPE_CHECKING, Optional

import pydantic
from graphene import Boolean, Field, InputObjectType, List, Mutation, String
from graphql import GraphQLResolveInfo
from infrahub_sdk.utils import extract_fields
from typing_extensions import Self

from infrahub import config, lock
from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.diff import BranchDiffer
from infrahub.core.merge import BranchMerger
from infrahub.core.migrations.schema.runner import schema_migrations_runner
from infrahub.exceptions import BranchNotFound
from infrahub.log import get_log_data, get_logger
from infrahub.message_bus import Meta, messages
from infrahub.services import services
from infrahub.worker import WORKER_IDENTITY

from ..types import BranchType

if TYPE_CHECKING:
    from .. import GraphqlContext


# pylint: disable=unused-argument

log = get_logger()


class BranchCreateInput(InputObjectType):
    id = String(required=False)
    name = String(required=True)
    description = String(required=False)
    origin_branch = String(required=False)
    branched_from = String(required=False)
    is_data_only = Boolean(required=False)


class BranchCreate(Mutation):
    class Arguments:
        data = BranchCreateInput(required=True)
        background_execution = Boolean(required=False)

    ok = Boolean()
    object = Field(BranchType)

    @classmethod
    async def mutate(
        cls, root: dict, info: GraphQLResolveInfo, data: BranchCreateInput, background_execution: bool = False
    ) -> Self:
        context: GraphqlContext = info.context

        # Check if the branch already exist
        try:
            await Branch.get_by_name(db=context.db, name=data["name"])
            raise ValueError(f"The branch {data['name']}, already exist")
        except BranchNotFound:
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

        log.info("created_branch", name=obj.name)
        log_data = get_log_data()
        request_id = log_data.get("request_id", "")

        ok = True

        fields = await extract_fields(info.field_nodes[0].selection_set)

        # Generate Event in message bus
        if config.SETTINGS.broker.enable and context.background:
            message = messages.EventBranchCreate(
                branch=obj.name,
                branch_id=str(obj.id),
                data_only=obj.is_data_only,
                meta=Meta(initiator_id=WORKER_IDENTITY, request_id=request_id),
            )
            context.background.add_task(services.send, message)

        return cls(object=await obj.to_graphql(fields=fields.get("object", {})), ok=ok)


class BranchNameInput(InputObjectType):
    name = String(required=False)


class BranchUpdateInput(InputObjectType):
    name = String(required=True)
    description = String(required=True)


class BranchDelete(Mutation):
    class Arguments:
        data = BranchNameInput(required=True)

    ok = Boolean()

    @classmethod
    async def mutate(cls, root: dict, info: GraphQLResolveInfo, data: BranchNameInput) -> Self:
        context: GraphqlContext = info.context

        obj = await Branch.get_by_name(db=context.db, name=data["name"])
        await obj.delete(db=context.db)

        if config.SETTINGS.broker.enable and context.background:
            log_data = get_log_data()
            request_id = log_data.get("request_id", "")
            message = messages.EventBranchDelete(
                branch=obj.name,
                branch_id=str(obj.id),
                data_only=obj.is_data_only,
                meta=Meta(request_id=request_id),
            )
            context.background.add_task(services.send, message)

        return cls(ok=True)


class BranchUpdate(Mutation):
    class Arguments:
        data = BranchUpdateInput(required=True)

    ok = Boolean()

    @classmethod
    async def mutate(cls, root: dict, info: GraphQLResolveInfo, data: BranchNameInput) -> Self:
        context: GraphqlContext = info.context

        obj = await Branch.get_by_name(db=context.db, name=data["name"])
        obj.description = data["description"]

        async with context.db.start_transaction() as db:
            await obj.save(db=db)

        return cls(ok=True)


class BranchRebase(Mutation):
    class Arguments:
        data = BranchNameInput(required=True)

    ok = Boolean()
    object = Field(BranchType)

    @classmethod
    async def mutate(cls, root: dict, info: GraphQLResolveInfo, data: BranchNameInput) -> Self:
        context: GraphqlContext = info.context

        obj = await Branch.get_by_name(db=context.db, name=data["name"])
        async with context.db.start_transaction() as db:
            await obj.rebase(db=db)

        fields = await extract_fields(info.field_nodes[0].selection_set)

        ok = True

        return cls(object=await obj.to_graphql(fields=fields.get("object", {})), ok=ok)


class BranchValidate(Mutation):
    class Arguments:
        data = BranchNameInput(required=True)

    ok = Boolean()
    messages = List(String)
    object = Field(BranchType)

    @classmethod
    async def mutate(cls, root: dict, info: GraphQLResolveInfo, data: BranchNameInput) -> Self:
        context: GraphqlContext = info.context

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

        return cls(object=await obj.to_graphql(fields=fields.get("object", {})), messages=validation_messages, ok=ok)


class BranchMerge(Mutation):
    class Arguments:
        data = BranchNameInput(required=True)

    ok = Boolean()
    object = Field(BranchType)

    @classmethod
    async def mutate(cls, root: dict, info: GraphQLResolveInfo, data: BranchNameInput) -> Self:
        context: GraphqlContext = info.context

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
                schema=merger.destination_schema,
                migrations=merger.migrations,
                service=context.service,
            )
            for error in errors:
                context.service.log.error(error)

        if config.SETTINGS.broker.enable and context.background:
            log_data = get_log_data()
            request_id = log_data.get("request_id", "")
            message = messages.EventBranchMerge(
                source_branch=obj.name,
                target_branch=config.SETTINGS.main.default_branch,
                meta=Meta(initiator_id=WORKER_IDENTITY, request_id=request_id),
            )
            context.background.add_task(services.send, message)

        return cls(object=await obj.to_graphql(fields=fields.get("object", {})), ok=ok)
