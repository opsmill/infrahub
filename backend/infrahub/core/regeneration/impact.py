from __future__ import annotations

from typing import TYPE_CHECKING, assert_never

from infrahub.core import registry
from infrahub.core.constants import InfrahubKind
from infrahub.core.validators.uniqueness.dependent_resolver import UniquenessDependentResolver
from infrahub.graphql.analyzer import InfrahubGraphQLQueryAnalyzer
from infrahub.graphql.execution import cached_parse
from infrahub.graphql.initialization import prepare_graphql_params
from infrahub.log import get_logger
from infrahub.message_bus.types import ProposedChangeSubscriber
from infrahub.workers.dependencies import get_database

from .impact_classifier import ChangedNodes, EveryTarget, QueryImpactClassifier, RelationshipReachedChanges
from .models import TargetSelection

log = get_logger()

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
    """Map data changes on `query_branch` to the subscribers a GraphQL query depends on.

    A change matters only when a modified field is one the query reads. The query analysis,
    the diff-summary tag and the subscriber lookup all run on `query_branch`, so the caller
    passes the branch the changed data lives on (a proposed change's source branch, a merge's
    target branch).

    `every_target` is the fallback when a change cannot be traced to specific subscribers;
    taking it as an argument keeps "process everything" out of the return type, so the caller
    always gets one authoritative list.
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

    readable_fields_by_kind = {kind: access.fields for kind, access in query_report.requested_read.items()}
    classifier = QueryImpactClassifier(
        query_branch=query_branch,
        only_has_unique_targets=query_report.only_has_unique_targets,
        traversed_kinds=query_report.traversed_kinds,
        readable_fields_by_kind=readable_fields_by_kind,
        reached_paths=query_report.relationship_reached_paths,
    )
    assessment = classifier.assess(diff_summary=diff_summary)

    log.debug(
        "SELECTIVE_REGEN field-impact: "
        f"branch={query_branch} subscriber_kind={subscriber_kind} "
        f"unique_targets={query_report.only_has_unique_targets} "
        f"readable_kinds={sorted(readable_fields_by_kind)} "
        f"traversed_kinds={sorted(query_report.traversed_kinds)} assessment={type(assessment).__name__}"
    )

    match assessment:
        case EveryTarget():
            return TargetSelection(ids=every_target, widened=True)
        case ChangedNodes(node_ids=node_ids):
            member_ids = node_ids
        case RelationshipReachedChanges():
            resolver = UniquenessDependentResolver(db=db, branch=query_branch_obj)
            member_ids = sorted(await _resolve_reached_members(changes=assessment, resolver=resolver))
        case _ as unreachable:
            assert_never(unreachable)

    subscribers = await _get_subscribers_for_nodes(node_ids=member_ids, branch=query_branch, client=client)
    ids = [subscriber.subscriber_id for subscriber in subscribers if subscriber.kind == subscriber_kind]
    log.debug(f"SELECTIVE_REGEN field-impact resolved subscribers: {len(ids)}")
    return TargetSelection(ids=ids, widened=False)


async def _resolve_reached_members(
    changes: RelationshipReachedChanges, resolver: UniquenessDependentResolverInterface
) -> set[str]:
    """Walk each change's relationship chain back to the group members that read it.

    Each hop resolves the current node ids to the owners referencing them, feeding the next hop, so
    a chain ends at the root members. Every hop returns a superset of the truly-related nodes, so the
    resolved member set is a superset too -- it never omits a member that genuinely needs to run.
    """
    members: set[str] = set(changes.direct_member_node_ids)
    for change in changes.reached:
        peer_uuids = set(change.node_ids)
        for hop in change.path.hops:
            if not peer_uuids:
                break
            peer_uuids = await resolver.resolve(
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
