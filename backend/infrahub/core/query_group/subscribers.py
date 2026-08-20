"""Resolution of the nodes subscribed to a GraphQL query group.

Kept free of any dependency beyond the SDK client so that consumers in unrelated packages
can share it without importing each other.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from infrahub.core.constants import InfrahubKind

if TYPE_CHECKING:
    from infrahub_sdk.client import InfrahubClient

GATHER_GRAPHQL_QUERY_SUBSCRIBERS = """
query GatherGraphQLQuerySubscribers($members: [ID!]) {
  CoreGraphQLQueryGroup(members__ids: $members) {
    edges {
      node {
        subscribers {
          edges {
            node {
              id
              __typename
            }
          }
        }
      }
    }
  }
}
"""


@dataclass(frozen=True, slots=True)
class SubscriberRef:
    """A node subscribed to a query group, as the gather query reports it."""

    id: str
    kind: str


async def fetch_subscriber_refs(*, client: InfrahubClient, node_ids: list[str], branch: str) -> list[SubscriberRef]:
    """Every node subscribed to a query group that has any of ``node_ids`` as a member.

    The same subscriber is reported once per matching group, so callers that cannot accept
    duplicates must deduplicate.
    """
    result = await client.execute_graphql(
        query=GATHER_GRAPHQL_QUERY_SUBSCRIBERS,
        branch_name=branch,
        variables={"members": node_ids},
    )
    return [
        SubscriberRef(id=subscriber["node"]["id"], kind=subscriber["node"]["__typename"])
        for group in result[InfrahubKind.GRAPHQLQUERYGROUP]["edges"]
        for subscriber in group["node"]["subscribers"]["edges"]
    ]
