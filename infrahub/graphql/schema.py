import asyncio

from datetime import datetime

import aio_pika
import aio_pika.abc
from aio_pika import DeliveryMode, ExchangeType, Message, connect

from graphene import Boolean, DateTime, Field, Int, List, ObjectType, Schema, String
from graphene.types.generic import GenericScalar

import infrahub.config as config

from .mutations import BranchCreate, BranchMerge, BranchRebase, BranchValidate
from .query import BranchDiffType, BranchType
from .utils import extract_fields


async def default_list_resolver(root, info, **kwargs):

    fields = await extract_fields(info.field_nodes[0].selection_set)
    return await info.return_type.of_type.graphene_type.get_list(**kwargs, fields=fields, context=info.context)


class InfrahubBaseQuery(ObjectType):

    branch = List(BranchType)

    diff = Field(BranchDiffType, branch=String(required=True))

    async def resolve_branch(self, info, **kwargs):
        fields = await extract_fields(info.field_nodes[0].selection_set)
        return await BranchType.get_list(fields=fields, **kwargs)

    async def resolve_diff(root, info, branch, **kwargs):
        fields = await extract_fields(info.field_nodes[0].selection_set)
        return await BranchDiffType.get_diff(fields=fields, branch=branch)


class InfrahubBaseMutation(ObjectType):

    branch_create = BranchCreate.Field()
    branch_rebase = BranchRebase.Field()
    branch_merge = BranchMerge.Field()
    branch_validate = BranchValidate.Field()


class InfrahubBaseSubscription(ObjectType):

    query = GenericScalar(name=String())

    async def subscribe_query(root, info, name):

        from . import execute_query

        at = info.context.get("infrahub_at")
        branch = info.context.get("infrahub_branch")

        connection = await aio_pika.connect_robust(
            host=config.SETTINGS.broker.address,
            login=config.SETTINGS.broker.username,
            password=config.SETTINGS.broker.password,
        )

        # Return the result of the query the first time
        result = await execute_query(name=name, branch=branch, at=at)
        yield result.data

        async with connection:

            # Creating a channel
            channel = await connection.channel()
            exchange_name = f"{config.SETTINGS.broker.namespace}.graph"
            exchange = await channel.declare_exchange(exchange_name, ExchangeType.FANOUT)

            # Declaring & Binding queue
            queue = await channel.declare_queue(exclusive=True)
            await queue.bind(exchange)

            async with queue.iterator() as queue_iter:
                # Cancel consuming after __aexit__
                async for message in queue_iter:
                    async with message.process():
                        result = await execute_query(name=name, branch=branch, at=at)
                        yield result.data
