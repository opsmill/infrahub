from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core import registry
from infrahub.core.constants import InfrahubKind
from infrahub.graphql.analyzer import InfrahubGraphQLQueryAnalyzer
from infrahub.graphql.execution import cached_parse
from infrahub.graphql.initialization import prepare_graphql_params
from infrahub.log import get_logger
from infrahub.message_bus.types import ProposedChangeSubscriber
from infrahub.workers.dependencies import get_database

from .impact_classifier import QueryImpactClassifier
from .models import ImpactedSubscribers, ImpactScope

log = get_logger()

if TYPE_CHECKING:
    from infrahub_sdk.client import InfrahubClient
    from infrahub_sdk.diff import NodeDiff


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
    client: InfrahubClient,
) -> ImpactedSubscribers:
    """Map data changes on a branch to the subscribers a GraphQL query actually depends on.

    A change is relevant only when at least one field that was modified is also read by the
    query. This lets us skip regeneration when, for example, only a `description` field changed
    but the query only reads `name` and `color`. The query analysis, the diff-summary branch tag,
    and the subscriber lookup all run against `query_branch`, so the caller passes the branch on
    which the changed data lives (the source branch for a proposed change, the merge target branch
    for a merge follow-up).

    Returns an `ImpactedSubscribers` whose scope is:
        SPECIFIC -- the query guarantees unique targets, so `ids` lists exactly the subscribers of
                    `subscriber_kind` linked to the changed nodes (possibly empty).
        ALL      -- the query does not guarantee unique targets but a relevant field changed, so the
                    caller cannot map the change to specific targets and must process every target.
        NONE     -- no node of a queried kind had any of its queried fields modified; nothing to do.
    """
    query_schema_branch = registry.schema.get_schema_branch(name=query_branch)
    query_branch_obj = registry.get_branch_from_registry(branch=query_branch)

    graphql_params = await prepare_graphql_params(db=await get_database(), branch=query_branch)
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
        root_kinds=query_report.root_kinds,
        readable_fields_by_kind=readable_fields_by_kind,
    )
    assessment = classifier.assess(diff_summary=diff_summary)

    log.debug(
        "SELECTIVE_REGEN field-impact: "
        f"branch={query_branch} subscriber_kind={subscriber_kind} "
        f"unique_targets={query_report.only_has_unique_targets} "
        f"readable_kinds={sorted(readable_fields_by_kind)} "
        f"root_kinds={sorted(query_report.root_kinds)} scope={assessment.scope.value}"
    )

    if assessment.scope is not ImpactScope.SPECIFIC:
        return ImpactedSubscribers(scope=assessment.scope)

    subscribers = await _get_subscribers_for_nodes(
        node_ids=assessment.changed_node_ids, branch=query_branch, client=client
    )
    ids = [subscriber.subscriber_id for subscriber in subscribers if subscriber.kind == subscriber_kind]
    log.debug(f"SELECTIVE_REGEN field-impact resolved subscribers: {len(ids)}")
    return ImpactedSubscribers(scope=assessment.scope, ids=ids)


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
