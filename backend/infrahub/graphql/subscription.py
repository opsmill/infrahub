from graphene import List, ObjectType, String
from graphene.types.generic import GenericScalar

import infrahub.config as config
from infrahub.message_bus import get_broker
from infrahub.message_bus.events import get_event_exchange

from .query import execute_query

# pylint: disable=


class EventType(ObjectType):
    type = String()
    action = String()
    body = GenericScalar()


class InfrahubBaseSubscription(ObjectType):
    query = GenericScalar(name=String(), params=GenericScalar(required=False))
    event = GenericScalar(topics=List(String, required=False))

    @staticmethod
    async def subscribe_query(
        root,  # pylint: disable=unused-argument
        info,
        name,
        params=None,
    ):
        at = info.context.get("infrahub_at")
        branch = info.context.get("infrahub_branch")
        db = info.context.get("infrahub_database")

        connection = await get_broker()

        # Return the result of the query the first time
        result = await execute_query(db=db, name=name, params=params, branch=branch, at=at)
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
                        result = await execute_query(db=db, name=name, params=params, branch=branch, at=at)
                        yield result.data

    @staticmethod
    async def subscribe_event(root, info, topics: List = None):  # pylint: disable=unused-argument
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
                        pass
                        # event = InfrahubMessage.convert(message=message)
                        # yield {"type": event.type.value, "action": event.action, "body": event.generate_message_body()}
