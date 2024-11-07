from pydantic import BaseModel, Field


class RequestGraphQLQueryGroupUpdate(BaseModel):
    """Sent to create or update a GraphQLQueryGroup associated with a given GraphQLQuery."""

    branch: str = Field(..., description="The branch to target")
    query_name: str = Field(..., description="The name of the GraphQLQuery that should be associated with the group")
    query_id: str = Field(..., description="The ID of the GraphQLQuery that should be associated with the group")
    related_node_ids: list[str] = Field(..., description="List of nodes related to the GraphQLQuery")
    subscribers: list[str] = Field(..., description="List of subscribers to add to the group")
    params: dict[str, str] = Field(..., description="Params sent with the query")
