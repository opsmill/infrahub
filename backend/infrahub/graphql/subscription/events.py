# import asyncio
# from typing import Any, Dict, Optional

# import graphene
# from graphene import Int, List, ObjectType, String, Field
# from graphene.types.generic import GenericScalar
# from graphql import GraphQLResolveInfo
# from graphql import graphql

# from infrahub.core import registry
# from infrahub.core.branch import Branch
# from infrahub.core.constants import InfrahubKind
# from infrahub.core.manager import NodeManager
# from infrahub.core.timestamp import Timestamp
# from infrahub.database import InfrahubDatabase
# from infrahub.log import get_logger

# from .graphql_query import execute_query, get_gql_query

# log = get_logger(name="infrahub.graphql")

# async def resolver_event(root: dict, info: GraphQLResolveInfo, topics: Optional[List] = None):
#     pass
# connection = await get_broker()

# async with connection:
#     # Creating a channel & Queue
#     channel = await connection.channel()
#     queue = await channel.declare_queue(exclusive=True)

#     # Get Event Exchange associated with this channel
#     exchange = await get_event_exchange(channel)

#     if topics:
#         for topic in topics:
#             # Binding queue to various topic related to this branch and eventually the main branch.
#             await queue.bind(exchange, routing_key=topic)
#     else:
#         await queue.bind(exchange, routing_key="#")

#     # TODO Add support for minimum interval to avoid sending updates too fast.
#     async with queue.iterator() as queue_iter:
#         # Cancel consuming after __aexit__
#         async for message in queue_iter:
#             async with message.process():
#                 pass
#                 # event = InfrahubMessage.convert(message=message)
#                 # yield {"type": event.type.value, "action": event.action, "body": event.generate_message_body()}
