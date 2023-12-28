from infrahub_sdk import Timestamp

from infrahub.log import get_logger
from infrahub.message_bus import messages
from infrahub.services import InfrahubServices

log = get_logger()


async def update(message: messages.RequestGraphQLQueryGroupUpdate, service: InfrahubServices) -> None:
    """Create or Update a GraphQLQueryGroup."""

    group_name = f"{message.query_name}__{message.params_hash}"
    group = await service.client.create(
        kind="CoreGraphQLQueryGroup",
        branch=message.branch,
        name=group_name,
        query=message.query_id,
        members=list(message.related_node_ids),
        subscribers=list(message.subscribers),
    )

    await group.create(at=Timestamp(), allow_update=True)
