from typing import TYPE_CHECKING

import pydantic
from graphene import Boolean, Field, InputObjectType, List, Mutation, String
from graphql import GraphQLResolveInfo

import infrahub.config as config
from infrahub import lock
from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.exceptions import BranchNotFound
from infrahub.log import get_log_data, get_logger
from infrahub.message_bus import Meta, messages
from infrahub.message_bus.events import (
    BranchMessageAction,
    InfrahubBranchMessage,
    send_event,
)
from infrahub.services import services
from infrahub.worker import WORKER_IDENTITY

from ..types import BranchType
from ..utils import extract_fields

if TYPE_CHECKING:
    from neo4j import AsyncSession

    from infrahub.message_bus.rpc import InfrahubRpcClient


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
    async def mutate(cls, root: dict, info: GraphQLResolveInfo, data: BranchCreateInput, background_execution=False):
        session: AsyncSession = info.context.get("infrahub_session")

        # Check if the branch already exist
        try:
            await Branch.get_by_name(session=session, name=data["name"])
            raise ValueError(f"The branch {data['name']}, already exist")
        except BranchNotFound:
            pass

        try:
            obj = Branch(**data)
        except pydantic.error_wrappers.ValidationError as exc:
            error_msgs = [f"invalid field {error['loc'][0]}: {error['msg']}" for error in exc.errors()]
            raise ValueError("\n".join(error_msgs)) from exc

        async with lock.registry.local_schema_lock():
            # Copy the schema from the origin branch and set the hash and the schema_changed_at value
            origin_schema = registry.schema.get_schema_branch(name=obj.origin_branch)
            new_schema = origin_schema.duplicate(name=obj.name)
            registry.schema.set_schema_branch(name=obj.name, schema=new_schema)
            obj.update_schema_hash()
            await obj.save(session=session)

        log.info("created_branch", name=obj.name)
        log_data = get_log_data()
        request_id = log_data.get("request_id", "")

        ok = True

        fields = await extract_fields(info.field_nodes[0].selection_set)

        # Generate Event in message bus
        if config.SETTINGS.broker.enable and info.context.get("background"):
            message = messages.EventBranchCreate(
                branch=obj.name,
                data_only=obj.is_data_only,
                meta=Meta(initiator_id=WORKER_IDENTITY, request_id=request_id),
            )
            info.context.get("background").add_task(services.send, message)

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
    async def mutate(cls, root: dict, info: GraphQLResolveInfo, data: BranchNameInput):
        session: AsyncSession = info.context.get("infrahub_session")

        obj = await Branch.get_by_name(session=session, name=data["name"])
        await obj.delete(session=session)
        return cls(ok=True)


class BranchUpdate(Mutation):
    class Arguments:
        data = BranchUpdateInput(required=True)

    ok = Boolean()

    @classmethod
    async def mutate(cls, root: dict, info: GraphQLResolveInfo, data: BranchNameInput):
        session: AsyncSession = info.context.get("infrahub_session")

        obj = await Branch.get_by_name(session=session, name=data["name"])
        obj.description = data["description"]

        await obj.save(session=session)
        return cls(ok=True)


class BranchRebase(Mutation):
    class Arguments:
        data = BranchNameInput(required=True)

    ok = Boolean()
    object = Field(BranchType)

    @classmethod
    async def mutate(cls, root: dict, info: GraphQLResolveInfo, data: BranchNameInput):
        session: AsyncSession = info.context.get("infrahub_session")

        obj = await Branch.get_by_name(session=session, name=data["name"])
        await obj.rebase(session=session)

        fields = await extract_fields(info.field_nodes[0].selection_set)

        ok = True

        if config.SETTINGS.broker.enable and info.context.get("background"):
            info.context.get("background").add_task(
                send_event, InfrahubBranchMessage(action=BranchMessageAction.REBASE, branch=obj.name)
            )

        return cls(object=await obj.to_graphql(fields=fields.get("object", {})), ok=ok)


class BranchValidate(Mutation):
    class Arguments:
        data = BranchNameInput(required=True)

    ok = Boolean()
    messages = List(String)
    object = Field(BranchType)

    @classmethod
    async def mutate(cls, root: dict, info: GraphQLResolveInfo, data: BranchNameInput):
        session: AsyncSession = info.context.get("infrahub_session")
        rpc_client: InfrahubRpcClient = info.context.get("infrahub_rpc_client")

        obj = await Branch.get_by_name(session=session, name=data["name"])
        ok, validation_messages = await obj.validate_branch(rpc_client=rpc_client, session=session)

        fields = await extract_fields(info.field_nodes[0].selection_set)

        return cls(object=await obj.to_graphql(fields=fields.get("object", {})), messages=validation_messages, ok=ok)


class BranchMerge(Mutation):
    class Arguments:
        data = BranchNameInput(required=True)

    ok = Boolean()
    object = Field(BranchType)

    @classmethod
    async def mutate(cls, root: dict, info: GraphQLResolveInfo, data: BranchNameInput):
        session: AsyncSession = info.context.get("infrahub_session")
        rpc_client: InfrahubRpcClient = info.context.get("infrahub_rpc_client")

        obj = await Branch.get_by_name(session=session, name=data["name"])

        async with lock.registry.global_graph_lock():
            await obj.merge(rpc_client=rpc_client, session=session)

            # Copy the schema from the origin branch and set the hash and the schema_changed_at value
            origin_branch = await obj.get_origin_branch(session=session)
            updated_schema = await registry.schema.load_schema_from_db(session=session, branch=origin_branch)
            registry.schema.set_schema_branch(name=origin_branch.name, schema=updated_schema)
            origin_branch.update_schema_hash()
            await origin_branch.save(session=session)

        fields = await extract_fields(info.field_nodes[0].selection_set)

        ok = True

        if config.SETTINGS.broker.enable and info.context.get("background"):
            info.context.get("background").add_task(
                send_event, InfrahubBranchMessage(action=BranchMessageAction.MERGE, branch=obj.name)
            )

        return cls(object=await obj.to_graphql(fields=fields.get("object", {})), ok=ok)
