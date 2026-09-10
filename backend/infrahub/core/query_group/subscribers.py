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
        query {
          node {
            id
          }
        }
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
    """A node subscribed to a query group, as the gather query reports it.

    ``query_id`` identifies the GraphQL query of the group that reported it, so a caller
    interested in one query can tell the groups apart. It is None when the group cannot be traced
    back to a query, which a caller must read as "unknown" and not as "another query".
    """

    id: str
    kind: str
    query_id: str | None = None


def _query_id(group: dict) -> str | None:
    """The id of the GraphQL query a group belongs to, or None when it cannot be read.

    The relationship is mandatory in the schema, but the peer it points at can be gone by the
    time the group is read, so the id is treated as optional here.
    """
    return ((group.get("query") or {}).get("node") or {}).get("id")


async def fetch_subscriber_refs(*, client: InfrahubClient, node_ids: list[str], branch: str) -> list[SubscriberRef]:
    """Every node subscribed to a query group that has any of ``node_ids`` as a member.

    The same subscriber is reported once per matching group, so callers that cannot accept
    duplicates must deduplicate. Each ref carries the id of its group's GraphQL query.
    """
    result = await client.execute_graphql(
        query=GATHER_GRAPHQL_QUERY_SUBSCRIBERS,
        branch_name=branch,
        variables={"members": node_ids},
    )
    return [
        SubscriberRef(
            id=subscriber["node"]["id"],
            kind=subscriber["node"]["__typename"],
            query_id=_query_id(group["node"]),
        )
        for group in result[InfrahubKind.GRAPHQLQUERYGROUP]["edges"]
        for subscriber in group["node"]["subscribers"]["edges"]
    ]
