from typing import List

from infrahub_sdk import InfrahubClient, InfrahubNode
from infrahub_sdk.utils import dict_hash

from infrahub.core.constants import InfrahubKind
from infrahub.log import get_logger
from infrahub.message_bus import messages
from infrahub.services import InfrahubServices

log = get_logger()


async def group_add_subscriber(client: InfrahubClient, group: InfrahubNode, subscribers: List[str], branch: str):
    subscribers_str = ["{ id: " + f'"{subscriber}"' + " }" for subscriber in subscribers]
    query = """
    mutation {
        RelationshipAdd(
            data: {
                id: "%s",
                name: "subscribers",
                nodes: [ %s ]
            }
        ) {
            ok
        }
    }
    """ % (
        group.id,
        ", ".join(subscribers_str),
    )

    return await client.execute_graphql(query=query, branch_name=branch, tracker="mutation-relationshipadd")


async def update(message: messages.RequestGraphQLQueryGroupUpdate, service: InfrahubServices) -> None:
    """Create or Update a GraphQLQueryGroup."""

    params_hash = dict_hash(message.params)
    group_name = f"{message.query_name}__{params_hash}"
    group_label = f"Query {message.query_name} Hash({params_hash[:8]})"
    group = await service.client.create(
        kind=InfrahubKind.GRAPHQLQUERYGROUP,
        branch=message.branch,
        name=group_name,
        label=group_label,
        query=message.query_id,
        parameters=message.params,
        members=message.related_node_ids,
    )
    await group.save(allow_upsert=True)

    if message.subscribers:
        await group_add_subscriber(
            client=service.client, group=group, subscribers=message.subscribers, branch=message.branch
        )
