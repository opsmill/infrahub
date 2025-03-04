from infrahub_sdk.groups import group_add_subscriber
from infrahub_sdk.utils import dict_hash
from prefect import flow

from infrahub.core.constants import InfrahubKind
from infrahub.groups.models import RequestGraphQLQueryGroupUpdate
from infrahub.services import InfrahubServices
from infrahub.workflows.utils import add_tags


@flow(name="graphql-query-group-update", flow_run_name="Update GraphQLQuery Group '{model.query_name}'")
async def update_graphql_query_group(model: RequestGraphQLQueryGroupUpdate, service: InfrahubServices) -> None:
    """Create or Update a GraphQLQueryGroup."""

    # If there is only one subscriber, associate the task to it
    # If there are more than one, for now we can't associate all of them
    related_nodes = []
    if len(model.subscribers) == 1:
        related_nodes.append(model.subscribers[0])

    await add_tags(branches=[model.branch], nodes=related_nodes)

    params_hash = dict_hash(model.params)
    group_name = f"{model.query_name}__{params_hash}"
    group_label = f"Query {model.query_name} Hash({params_hash[:8]})"
    group = await service.client.create(
        kind=InfrahubKind.GRAPHQLQUERYGROUP,
        branch=model.branch,
        name=group_name,
        label=group_label,
        group_type="internal",
        query=model.query_id,
        parameters=model.params,
        members=model.related_node_ids,
    )
    await group.save(allow_upsert=True)

    if model.subscribers:
        await group_add_subscriber(
            client=service.client, group=group, subscribers=model.subscribers, branch=model.branch
        )
