from infrahub_sdk.groups import group_add_subscriber
from infrahub_sdk.utils import dict_hash
from prefect import flow

from infrahub.core.constants import InfrahubKind
from infrahub.groups.models import RequestGraphQLQueryGroupUpdate
from infrahub.workers.dependencies import get_client
from infrahub.workflows.utils import add_tags


@flow(name="graphql-query-group-update", flow_run_name="Update GraphQLQuery Group '{model.query_name}'")
async def update_graphql_query_group(model: RequestGraphQLQueryGroupUpdate) -> None:
    """Create or Update a GraphQLQueryGroup."""
    client = get_client()

    await add_tags(branches=[model.branch], nodes=model.related_nodes, namespace=False)

    params_hash = dict_hash(model.params)
    group_name = f"{model.query_name}__{params_hash}"
    group_label = f"Query {model.query_name} Hash({params_hash[:8]})"
    group = await client.create(
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
        await group_add_subscriber(client=client, group=group, subscribers=model.subscribers, branch=model.branch)
