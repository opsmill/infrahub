from graphene import (
    Boolean,
    Field,
    InputObjectType,
    Int,
    List,
    Mutation,
    String,
)

import aio_pika
from aio_pika import DeliveryMode, ExchangeType, Message, connect
from aio_pika.abc import AbstractRobustConnection, AbstractChannel, AbstractExchange

from graphene.types.mutation import MutationOptions

from infrahub.broker import get_broker

import infrahub.config as config
from infrahub.core.branch import Branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.schema import NodeSchema
from infrahub.exceptions import BranchNotFound, NodeNotFound
from infrahub.broker import get_broker

from .query import BranchType
from .types import Any
from .utils import extract_fields


# ------------------------------------------
# Infrahub GraphQLType
# ------------------------------------------
class InfrahubMutationOptions(MutationOptions):
    schema = None


class InfrahubMutation(Mutation):
    @classmethod
    def __init_subclass_with_meta__(cls, schema: NodeSchema = None, _meta=None, **options):

        # Make sure schema is a valid NodeSchema Node Class
        if not isinstance(schema, NodeSchema):
            raise ValueError(f"You need to pass a valid NodeSchema in '{cls.__name__}.Meta', received '{schema}'")

        if not _meta:
            _meta = InfrahubMutationOptions(cls)

        _meta.schema = schema

        super().__init_subclass_with_meta__(_meta=_meta, **options)

    @classmethod
    async def mutate(cls, root, info, *args, **kwargs):

        at = info.context.get("infrahub_at")
        branch = info.context.get("infrahub_branch")
        # account = info.context.get("infrahub_account", None)

        if "Create" in cls.__name__:
            return await cls.mutate_create(root, info, branch=branch, at=at, *args, **kwargs)
        elif "Update" in cls.__name__:
            return await cls.mutate_update(root, info, branch=branch, at=at, *args, **kwargs)
        elif "Delete" in cls.__name__:
            return await cls.mutate_delete(root, info, branch=branch, at=at, *args, **kwargs)

        raise NotImplementedError

    @classmethod
    async def mutate_create(cls, root, info, data, branch=None, at=None):

        obj = Node(cls._meta.schema, branch=branch, at=at).new(**data).save()

        fields = await extract_fields(info.field_nodes[0].selection_set)
        ok = True

        # broker = await get_broker().__anext__()

        connection = await aio_pika.connect_robust(
            host=config.SETTINGS.broker.address,
            login=config.SETTINGS.broker.username,
            password=config.SETTINGS.broker.password,
        )

        channel = await connection.channel()
        exchange_name = f"{config.SETTINGS.broker.namespace}.graph"
        exchange = await channel.declare_exchange(exchange_name, ExchangeType.FANOUT)

        message = Message(
            body="created/{}".format(obj.id).encode(),
            delivery_mode=DeliveryMode.PERSISTENT,
        )

        await exchange.publish(message, routing_key=config.SETTINGS.broker.namespace)

        return cls(object=obj.to_graphql(fields=fields.get("object", {})), ok=ok)

    @classmethod
    async def mutate_update(cls, root, info, data, branch=None, at=None):

        if not (obj := NodeManager.get_one(data.get("id"), branch=branch, at=at)):
            raise NodeNotFound(branch, cls._meta.schema.kind, data.get("id"))

        obj.from_graphql(data)
        obj.save()

        ok = True

        fields = await extract_fields(info.field_nodes[0].selection_set)

        return cls(object=obj.to_graphql(fields=fields.get("object", {})), ok=ok)

    @classmethod
    async def mutate_delete(cls, root, info, data, branch=None, at=None):

        if not (obj := NodeManager.get_one(data.get("id"), branch=branch, at=at)):
            raise NodeNotFound(branch, cls._meta.schema.kind, data.get("id"))

        obj.delete()
        ok = True

        return cls(ok=ok)


# --------------------------------------------------------------------------------


class BaseAttributeInput(InputObjectType):
    id = String(required=False)
    is_visible = Boolean(required=False)
    # criticality = Field(CriticalityInput, required=False)


class StringAttributeInput(InputObjectType):
    source = String(required=False)
    value = String(required=False)
    id = String(required=False)


class IntAttributeInput(InputObjectType):
    source = String(required=False)
    value = Int(required=False)
    id = String(required=False)


class BoolAttributeInput(InputObjectType):
    source = String(required=False)
    value = Boolean(required=False)
    id = String(required=False)


class AnyAttributeInput(InputObjectType):
    source = String(required=False)
    value = Any(required=False)
    id = String(required=False)


class RemoteAttributeInput(InputObjectType):
    source = String(required=False)
    value = String(required=False)


# --------------------------------------------------
# Mutations Specific to Branch
# --------------------------------------------------


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

    ok = Boolean()
    object = Field(BranchType)

    @classmethod
    async def mutate(cls, root, info, data):

        # Check if the branch already exist
        try:
            Branch.get_by_name(data["name"])
            raise ValueError(f"The branch {data['name']}, already exist")
        except BranchNotFound:
            pass

        obj = Branch(**data)
        obj.save()

        if not obj.is_data_only:
            # Query all repositories and add a branch on each one of them too
            repositories = NodeManager.query("Repository")
            for repo in repositories:
                repo.add_branch(obj.name)

        ok = True

        fields = await extract_fields(info.field_nodes[0].selection_set)

        return cls(object=obj.to_graphql(fields=fields.get("object", {})), ok=ok)


class BranchNameInput(InputObjectType):
    name = String(required=False)


class BranchRebase(Mutation):
    class Arguments:
        data = BranchNameInput(required=True)

    ok = Boolean()
    object = Field(BranchType)

    @classmethod
    async def mutate(cls, root, info, data):
        obj = Branch.get_by_name(data["name"])
        obj.rebase()

        fields = await extract_fields(info.field_nodes[0].selection_set)

        ok = True

        return cls(object=obj.to_graphql(fields=fields.get("object", {})), ok=ok)


class BranchValidate(Mutation):
    class Arguments:
        data = BranchNameInput(required=True)

    ok = Boolean()
    messages = List(String)
    object = Field(BranchType)

    @classmethod
    async def mutate(cls, root, info, data):
        obj = Branch.get_by_name(data["name"])
        ok, messages = obj.validate()

        fields = await extract_fields(info.field_nodes[0].selection_set)

        return cls(object=obj.to_graphql(fields=fields.get("object", {})), messages=messages, ok=ok)


class BranchMerge(Mutation):
    class Arguments:
        data = BranchNameInput(required=True)

    ok = Boolean()
    object = Field(BranchType)

    @classmethod
    async def mutate(cls, root, info, data):
        obj = Branch.get_by_name(data["name"])
        obj.merge()

        fields = await extract_fields(info.field_nodes[0].selection_set)

        ok = True

        return cls(object=obj.to_graphql(fields=fields.get("object", {})), ok=ok)
