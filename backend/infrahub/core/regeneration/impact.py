from __future__ import annotations

from typing import TYPE_CHECKING, assert_never

from infrahub.core import registry
from infrahub.core.query_group.subscribers import fetch_subscriber_refs
from infrahub.core.relationship.dependent_resolver import QueryDependentNodeResolver
from infrahub.graphql.analyzer import InfrahubGraphQLQueryAnalyzer
from infrahub.graphql.execution import cached_parse

from .classifier_builder import QueryClassifierBuilder
<<<<<<< HEAD
from .derived_dependencies import SchemaDerivedFieldDependencyResolver
=======
from .filtered_peers import ChangedNodeIndex, FilteredPeerReads, FilteredRelationshipExclusions
>>>>>>> origin/stable
from .impact_classifier import ChangedNodes, EveryTarget, RelationshipReachedChanges
from .models import TargetSelection
from .peer_query import RelationshipPeerQuery

if TYPE_CHECKING:
    from infrahub_sdk.client import InfrahubClient
    from infrahub_sdk.diff import NodeDiff

<<<<<<< HEAD
    from infrahub.core.relationship.dependent_resolver import DependentNodeResolver
    from infrahub.database import InfrahubDatabase
=======
>>>>>>> origin/stable
    from infrahub.graphql.analyzer import GraphQLQueryReport


class FieldLevelImpactResolver:
    """Map data changes on a branch to the subscribers a GraphQL query depends on.

<<<<<<< HEAD
    A change matters only when a modified field is one the query reads. The caller analyzes the query
    against the branch passed to `resolve`, and the diff-summary tag and the subscriber lookup run on it
    too, so the caller passes the branch the changed data lives on (a proposed change's source branch, a
    merge's target branch).
=======

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
>>>>>>> origin/stable
    """

<<<<<<< HEAD
    def __init__(self, db: InfrahubDatabase, client: InfrahubClient) -> None:
        self.db = db
        self.client = client

    def analyze(self, *, query_payload: str, query_branch: str) -> GraphQLQueryReport:
        """What the query reads, from its text analyzed against the query branch schema."""
        return InfrahubGraphQLQueryAnalyzer(
            query=query_payload,
            branch=registry.get_branch_from_registry(branch=query_branch),
            schema_branch=registry.schema.get_schema_branch(name=query_branch),
            document=cached_parse(query_payload),
        ).query_report

    async def resolve(
        self,
        *,
        query_report: GraphQLQueryReport,
        diff_summary: list[NodeDiff],
        query_branch: str,
        subscriber_kind: str,
        every_target: list[str],
    ) -> TargetSelection:
        """Return the subscribers a change implicates, widening to `every_target` when it cannot narrow.

        `every_target` is the fallback when a change cannot be traced to specific subscribers;
        taking it as an argument keeps "process everything" out of the return type, so the caller
        always gets one authoritative list.
        """
        query_schema_branch = registry.schema.get_schema_branch(name=query_branch)
        query_branch_obj = registry.get_branch_from_registry(branch=query_branch)

        dependency_resolver = SchemaDerivedFieldDependencyResolver(schema_branch=query_schema_branch)
        classifier = QueryClassifierBuilder(
            query_branch=query_branch, schema_branch=query_schema_branch, dependency_resolver=dependency_resolver
        ).build(query_report)
        assessment = classifier.assess(diff_summary=diff_summary)
=======
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
>>>>>>> origin/stable

        match assessment:
            case EveryTarget(widening=widening):
                return TargetSelection(ids=every_target, widening=widening)
            case ChangedNodes(node_ids=node_ids):
                member_ids = node_ids
            case RelationshipReachedChanges():
<<<<<<< HEAD
                dependent_resolver = QueryDependentNodeResolver(db=self.db, branch=query_branch_obj)
                member_ids = sorted(await ReachedMemberResolver(resolver=dependent_resolver).resolve(assessment))
=======
                member_ids = sorted(await ReachedMemberResolver(peer_reads=peer_reads).resolve(assessment))
>>>>>>> origin/stable
            case _ as unreachable:
                assert_never(unreachable)

        subscribers = await fetch_subscriber_refs(client=self.client, node_ids=member_ids, branch=query_branch)
        ids = [subscriber.id for subscriber in subscribers if subscriber.kind == subscriber_kind]
        return TargetSelection(ids=ids)


class ReachedMemberResolver:
    """Walk each relationship-reached change back to the group members that read it.

    Each hop resolves the current node ids to the owners whose read of the hop's relationship can return
    them, feeding the next hop, so a chain ends at the root members. Every hop returns a superset of the
    truly-related nodes, so the resolved member set is a superset too.
    """

<<<<<<< HEAD
    def __init__(self, *, resolver: DependentNodeResolver) -> None:
        self.resolver = resolver
=======
    def __init__(self, *, peer_reads: FilteredPeerReads) -> None:
        self.peer_reads = peer_reads
>>>>>>> origin/stable

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
