from pydantic import Field

from infrahub.message_bus import InfrahubMessage


class RequestGraphQLQueryGroupUpdate(InfrahubMessage):
    """Sent to create or update a GraphQLQueryGroup associated with a given GraphQLQuery."""

    branch: str = Field(..., description="The branch to target")
    query_name: str = Field(..., description="The name of the GraphQLQuery that should be associated with the group")
    query_id: str = Field(..., description="The ID of the GraphQLQuery that should be associated with the group")
    related_node_ids: set[str] = Field(..., description="List of nodes related to the GraphQLQuery")
    subscribers: set[str] = Field(..., description="List of subscribers to add to the group")
    params_hash: str = Field(..., description="Hash representation of the params sent with the query")
