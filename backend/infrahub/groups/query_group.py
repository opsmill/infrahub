from __future__ import annotations

from typing import TYPE_CHECKING, Any

from infrahub_sdk.utils import dict_hash

from infrahub.graphql.execution import execute_graphql_query
from infrahub.graphql.initialization import prepare_graphql_params
from infrahub.graphql.middleware import raise_on_mutation_for_branch_status
from infrahub.graphql.utils import extract_data

if TYPE_CHECKING:
    from infrahub.auth.session import AccountSession
    from infrahub.database import InfrahubDatabase
    from infrahub.graphql.initialization import GraphqlParams
    from infrahub.groups.models import RequestGraphQLQueryGroupUpdate
    from infrahub.services import InfrahubServices

UPSERT_QUERY_GROUP = """
mutation UpsertGraphQLQueryGroup(
    $name: String!, $label: String!, $query: String!, $parameters: GenericScalar, $members: [RelatedNodeInput]
) {
    CoreGraphQLQueryGroupUpsert(
        data: {
            name: { value: $name }
            label: { value: $label }
            group_type: { value: "internal" }
            query: { id: $query }
            parameters: { value: $parameters }
            members: $members
        }
    ) {
        object { id }
    }
}
"""

ADD_QUERY_GROUP_SUBSCRIBERS = """
mutation AddGraphQLQueryGroupSubscribers($group: String!, $subscribers: [RelatedNodeInput]) {
    RelationshipAdd(data: { id: $group, name: "subscribers", nodes: $subscribers }) { ok }
}
"""


async def save_graphql_query_group(
    db: InfrahubDatabase,
    model: RequestGraphQLQueryGroupUpdate,
    account_session: AccountSession,
    service: InfrahubServices,
) -> None:
    """Create or update the group of the nodes a stored query read, and add its subscribers to it.

    Raises:
        GraphQLQueryError: When the branch does not accept mutations or a mutation fails.

    """
    gql_params = await prepare_graphql_params(
        db=db, branch=model.branch, account_session=account_session, service=service
    )
    params_hash = dict_hash(model.params)
    upserted = await _run_mutation(
        gql_params=gql_params,
        name="UpsertGraphQLQueryGroup",
        source=UPSERT_QUERY_GROUP,
        variables={
            "name": f"{model.query_name}__{params_hash}",
            "label": f"Query {model.query_name} Hash({params_hash[:8]})",
            "query": model.query_id,
            "parameters": model.params,
            "members": [{"id": node_id} for node_id in model.related_node_ids],
        },
    )
    if not model.subscribers:
        return

    await _run_mutation(
        gql_params=gql_params,
        name="AddGraphQLQueryGroupSubscribers",
        source=ADD_QUERY_GROUP_SUBSCRIBERS,
        variables={
            "group": upserted["CoreGraphQLQueryGroupUpsert"]["object"]["id"],
            "subscribers": [{"id": subscriber} for subscriber in model.subscribers],
        },
    )


async def _run_mutation(gql_params: GraphqlParams, name: str, source: str, variables: dict[str, Any]) -> dict[str, Any]:
    result = await execute_graphql_query(
        schema=gql_params.schema,
        source=source,
        context_value=gql_params.context,
        root_value=None,
        variable_values=variables,
        middleware=[raise_on_mutation_for_branch_status],
    )
    return extract_data(query_name=name, result=result)
