from __future__ import annotations

from typing import TYPE_CHECKING, assert_never

from infrahub.core import registry
from infrahub.core.query_group.subscribers import fetch_subscriber_refs
from infrahub.core.relationship.dependent_resolver import DependentNodeResolver
from infrahub.graphql.analyzer import InfrahubGraphQLQueryAnalyzer
from infrahub.graphql.execution import cached_parse
from infrahub.graphql.initialization import prepare_graphql_params
from infrahub.workers.dependencies import get_database

from .impact_classifier import ChangedNodes, EveryTarget, QueryImpactClassifier, RelationshipReachedChanges
from .models import TargetSelection

if TYPE_CHECKING:
    from infrahub_sdk.client import InfrahubClient
    from infrahub_sdk.diff import NodeDiff

    from infrahub.core.relationship.dependent_resolver import DependentNodeResolverInterface


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
        reached_paths_by_kind=query_report.relationship_reached_paths_by_kind,
    )
    assessment = classifier.assess(diff_summary=diff_summary)

    match assessment:
        case EveryTarget():
            return TargetSelection(ids=every_target, widened=True)
        case ChangedNodes(node_ids=node_ids):
            member_ids = node_ids
        case RelationshipReachedChanges():
            dependent_resolver = DependentNodeResolver(db=db, branch=query_branch_obj)
            member_ids = sorted(await ReachedMemberResolver(resolver=dependent_resolver).resolve(assessment))
        case _ as unreachable:
            assert_never(unreachable)

    subscribers = await fetch_subscriber_refs(client=client, node_ids=member_ids, branch=query_branch)
    ids = [subscriber.id for subscriber in subscribers if subscriber.kind == subscriber_kind]
    return TargetSelection(ids=ids, widened=False)


class ReachedMemberResolver:
    """Walk each relationship-reached change back to the group members that read it.

    Each hop resolves the current node ids to the owners referencing them, feeding the next hop, so
    a chain ends at the root members. Every hop returns a superset of the truly-related nodes, so the
    resolved member set is a superset too.
    """

    def __init__(self, *, resolver: DependentNodeResolverInterface) -> None:
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
