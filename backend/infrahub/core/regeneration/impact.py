from __future__ import annotations

from typing import TYPE_CHECKING, assert_never

from infrahub.core import registry
from infrahub.core.constants import InfrahubKind
from infrahub.core.validators.uniqueness.dependent_resolver import UniquenessDependentResolver
from infrahub.message_bus.types import ProposedChangeSubscriber
from infrahub.workers.dependencies import get_database

from .classifier_builder import QueryClassifierBuilder
from .filtered_peers import ChangedNodeIndex, FilteredPeerReads, FilteredRelationshipExclusions
from .impact_classifier import ChangedNodes, EveryTarget, RelationshipReachedChanges
from .models import TargetSelection
from .peer_query import RelationshipPeerQuery

if TYPE_CHECKING:
    from infrahub_sdk.client import InfrahubClient
    from infrahub_sdk.diff import NodeDiff

    from infrahub.graphql.analyzer import GraphQLQueryReport


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
    query_report: GraphQLQueryReport,
    diff_summary: list[NodeDiff],
    query_branch: str,
    subscriber_kind: str,
    every_target: list[str],
    client: InfrahubClient,
) -> TargetSelection:
    """Map data changes on a branch to the subscribers a GraphQL query actually depends on.

    A change is relevant only when at least one field that was modified is also read by the
    query. This lets us skip regeneration when, for example, only a `description` field changed
    but the query only reads `name` and `color`. The caller analyzes the query against
    `query_branch`, and the diff-summary branch tag and the subscriber lookup run against it too,
    so the caller passes the branch on which the changed data lives (the source branch for a
    proposed change, the merge target branch for a merge follow-up).

    `every_target` is what the caller must fall back to when a change cannot be traced to specific
    subscribers. Taking it as an argument keeps that fallback out of the return type: the caller
    always receives one authoritative list and never has to resolve a "process everything" case.
    Only the narrowed outcome costs a subscriber lookup.

    A filtered relationship read, such as `prefixes(role__value: "aggregate")`, only sees the peers
    that pass its filters, so a change to a peer that fails them before and after is left out.
    """
    db = await get_database()
    query_schema_branch = registry.schema.get_schema_branch(name=query_branch)
    query_branch_obj = registry.get_branch_from_registry(branch=query_branch)

    classifier = QueryClassifierBuilder(query_branch=query_branch, schema_branch=query_schema_branch).build(
        query_report
    )

    # The worker's database object is shared by concurrent flows, so the reads below use their own session.
    async with db.start_session(read_only=True) as session_db:
        changes = ChangedNodeIndex.from_diff(diff_summary=diff_summary, query_branch=query_branch)
        peer_reads = FilteredPeerReads(
            changes=changes,
            dependents=UniquenessDependentResolver(db=session_db, branch=query_branch_obj),
            peers=RelationshipPeerQuery(db=session_db, branch=query_branch_obj, schema_branch=query_schema_branch),
        )
        exclusions = FilteredRelationshipExclusions(
            reads=query_report.relationship_reads,
            schema_branch=query_schema_branch,
            changes=changes,
            peer_reads=peer_reads,
        )
        excluded_changes = (
            await exclusions.excluded_changes(diff_summary=diff_summary)
            if exclusions.has_filtered_reads and not classifier.depends_on_everything
            else frozenset()
        )
        assessment = classifier.assess(diff_summary=diff_summary, excluded_changes=excluded_changes)

        match assessment:
            case EveryTarget(widening=widening):
                return TargetSelection(ids=every_target, widening=widening)
            case ChangedNodes(node_ids=node_ids):
                member_ids = node_ids
            case RelationshipReachedChanges():
                member_ids = sorted(await ReachedMemberResolver(peer_reads=peer_reads).resolve(assessment))
            case _ as unreachable:
                assert_never(unreachable)

    subscribers = await _get_subscribers_for_nodes(node_ids=member_ids, branch=query_branch, client=client)
    ids = [subscriber.subscriber_id for subscriber in subscribers if subscriber.kind == subscriber_kind]
    return TargetSelection(ids=ids)


class ReachedMemberResolver:
    """Walk each relationship-reached change back to the group members that read it.

    Each hop resolves the current node ids to the owners whose read of the hop's relationship can return
    them, feeding the next hop, so a chain ends at the root members. Every hop returns a superset of the
    truly-related nodes, so the resolved member set is a superset too.
    """

    def __init__(self, *, peer_reads: FilteredPeerReads) -> None:
        self.peer_reads = peer_reads

    async def resolve(self, changes: RelationshipReachedChanges) -> set[str]:
        members: set[str] = set(changes.direct_member_node_ids)
        for change in changes.reached:
            for path in change.paths:
                peer_uuids = set(change.node_ids)
                for hop in path.hops:
                    if not peer_uuids:
                        break
                    peer_uuids = await self.peer_reads.owners(hop=hop, peer_ids=peer_uuids)
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
