from typing_extensions import Required
import aio_pika
import aio_pika.abc

from graphene import Boolean, DateTime, Field, Int, List, ObjectType, Schema, String
from graphene.types.generic import GenericScalar

import infrahub.config as config
from infrahub.message_bus import get_broker
from infrahub.message_bus.events import get_event_exchange, Event


class EventType(ObjectType):
    type = String()
    action = String()
    body = GenericScalar()


class InfrahubBaseSubscription(ObjectType):

    query = GenericScalar(name=String(), params=GenericScalar(required=False), min_interval=Int(required=False))
    event = GenericScalar(topics=List(String, required=False))

    async def subscribe_query(
        root,
        info,
        name,
        min_interval=5,
        params=None,
    ):

        from . import execute_query

        at = info.context.get("infrahub_at")
        branch = info.context.get("infrahub_branch")

        connection = await get_broker()

        # Return the result of the query the first time
        result = await execute_query(name=name, params=params, branch=branch, at=at)
        yield result.data

        async with connection:

            # Creating a channel & Queue
            channel = await connection.channel()
            queue = await channel.declare_queue(exclusive=True)

            # Get Event Exchange associated with this channel
            exchange = await get_event_exchange(channel)

            # Binding queue to various topic related to this branch and eventually the main branch.
            await queue.bind(exchange, routing_key=f"data.{branch.name}.#")
            await queue.bind(exchange, routing_key=f"branch.{branch.name}.#")

            if branch.name != config.SETTINGS.main.default_branch:
                await queue.bind(exchange, routing_key=f"data.{config.SETTINGS.main.default_branch}.#")
                await queue.bind(exchange, routing_key=f"branch.{config.SETTINGS.main.default_branch}.#")

            # TODO Add support for minimum interval to avoid sending updates too fast.
            async with queue.iterator() as queue_iter:
                # Cancel consuming after __aexit__
                async for message in queue_iter:
                    async with message.process():
                        result = await execute_query(name=name, params=params, branch=branch, at=at)
                        yield result.data

    async def subscribe_event(root, info, topics: List = None):

        connection = await get_broker()

        async with connection:

            # Creating a channel & Queue
            channel = await connection.channel()
            queue = await channel.declare_queue(exclusive=True)

            # Get Event Exchange associated with this channel
            exchange = await get_event_exchange(channel)

            if topics:
                for topic in topics:
                    # Binding queue to various topic related to this branch and eventually the main branch.
                    await queue.bind(exchange, routing_key=topic)
            else:
                await queue.bind(exchange, routing_key="#")

            # TODO Add support for minimum interval to avoid sending updates too fast.
            async with queue.iterator() as queue_iter:
                # Cancel consuming after __aexit__
                async for message in queue_iter:
                    async with message.process():
                        event = Event.init(message)
                        yield {"type": event.type.value, "action": event.action, "body": event.generate_message_body()}
