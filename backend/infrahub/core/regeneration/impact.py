from __future__ import annotations

from typing import TYPE_CHECKING, assert_never

from infrahub.core import registry
from infrahub.core.constants import InfrahubKind
from infrahub.core.validators.uniqueness.dependent_resolver import UniquenessDependentResolver
from infrahub.graphql.analyzer import InfrahubGraphQLQueryAnalyzer
from infrahub.graphql.execution import cached_parse
from infrahub.graphql.initialization import prepare_graphql_params
from infrahub.message_bus.types import ProposedChangeSubscriber
from infrahub.workers.dependencies import get_database

from .classifier_builder import QueryClassifierBuilder
from .impact_classifier import ChangedNodes, EveryTarget, RelationshipReachedChanges
from .models import TargetSelection

if TYPE_CHECKING:
    from infrahub_sdk.client import InfrahubClient
    from infrahub_sdk.diff import NodeDiff

    from infrahub.core.validators.uniqueness.dependent_resolver import UniquenessDependentResolverInterface


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


async def get_field_level_impacted_subscribers(
    query_payload: str,
    diff_summary: list[NodeDiff],
    query_branch: str,
    subscriber_kind: str,
    every_target: list[str],
    client: InfrahubClient,
) -> TargetSelection:
    """Map data changes on a branch to the subscribers a GraphQL query actually depends on.

    A change is relevant only when at least one field that was modified is also read by the
    query. This lets us skip regeneration when, for example, only a `description` field changed
    but the query only reads `name` and `color`. The query analysis, the diff-summary branch tag,
    and the subscriber lookup all run against `query_branch`, so the caller passes the branch on
    which the changed data lives (the source branch for a proposed change, the merge target branch
    for a merge follow-up).

    `every_target` is what the caller must fall back to when a change cannot be traced to specific
    subscribers. Taking it as an argument keeps that fallback out of the return type: the caller
    always receives one authoritative list and never has to resolve a "process everything" case.
    Only the narrowed outcome costs a subscriber lookup.
    """
    db = await get_database()
    query_schema_branch = registry.schema.get_schema_branch(name=query_branch)
    query_branch_obj = registry.get_branch_from_registry(branch=query_branch)

    graphql_params = await prepare_graphql_params(db=db, branch=query_branch)
    query_report = InfrahubGraphQLQueryAnalyzer(
        query=query_payload,
        branch=query_branch_obj,
        schema_branch=query_schema_branch,
        schema=graphql_params.schema,
        document=cached_parse(query_payload),
    ).query_report

    classifier = QueryClassifierBuilder(query_branch=query_branch, schema_branch=query_schema_branch).build(
        query_report
    )
    assessment = classifier.assess(diff_summary=diff_summary)

    match assessment:
        case EveryTarget(widening=widening):
            return TargetSelection(ids=every_target, widening=widening)
        case ChangedNodes(node_ids=node_ids):
            member_ids = node_ids
        case RelationshipReachedChanges():
            dependent_resolver = UniquenessDependentResolver(db=db, branch=query_branch_obj)
            member_ids = sorted(await ReachedMemberResolver(resolver=dependent_resolver).resolve(assessment))
        case _ as unreachable:
            assert_never(unreachable)

    subscribers = await _get_subscribers_for_nodes(node_ids=member_ids, branch=query_branch, client=client)
    ids = [subscriber.subscriber_id for subscriber in subscribers if subscriber.kind == subscriber_kind]
    return TargetSelection(ids=ids)


class ReachedMemberResolver:
    """Walk each relationship-reached change back to the group members that read it.

    Each hop resolves the current node ids to the owners referencing them, feeding the next hop, so
    a chain ends at the root members. Every hop returns a superset of the truly-related nodes, so the
    resolved member set is a superset too.
    """

    def __init__(self, *, resolver: UniquenessDependentResolverInterface) -> None:
        self.resolver = resolver

    async def resolve(self, changes: RelationshipReachedChanges) -> set[str]:
        members: set[str] = set(changes.direct_member_node_ids)
        for change in changes.reached:
            for path in change.paths:
                peer_uuids = set(change.node_ids)
                for hop in path.hops:
                    if not peer_uuids:
                        break
                    peer_uuids = await self.resolver.resolve(
                        node_kind=hop.node_kind,
                        relationship_identifier=hop.relationship_identifier,
                        relationship_direction=hop.relationship_direction,
                        peer_uuids=sorted(peer_uuids),
                    )
                members |= peer_uuids
        return members


async def _get_subscribers_for_nodes(
    node_ids: list[str], branch: str, client: InfrahubClient
) -> list[ProposedChangeSubscriber]:
    result = await client.execute_graphql(
        query=GATHER_GRAPHQL_QUERY_SUBSCRIBERS,
        branch_name=branch,
        variables={"members": node_ids},
    )
    subscribers = []
    for group in result[InfrahubKind.GRAPHQLQUERYGROUP]["edges"]:
        for subscriber in group["node"]["subscribers"]["edges"]:
            subscribers.append(
                ProposedChangeSubscriber(subscriber_id=subscriber["node"]["id"], kind=subscriber["node"]["__typename"])
            )
    return subscribers
