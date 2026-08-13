from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from .predicates import relevant_node_changes

if TYPE_CHECKING:
    from infrahub_sdk.diff import NodeDiff

    from infrahub.graphql.analyzer import ReachedPath


@dataclass(frozen=True, slots=True)
class EveryTarget:
    """The changed nodes cannot be traced back to specific targets, so every one must be processed.

    Carries no ids because there are none to carry: the affected targets are unknown at this point,
    which is why the caller has to fall back to its own full set.
    """


@dataclass(frozen=True, slots=True)
class ChangedNodes:
    """These changed nodes map onto group members, so their subscribers can be resolved.

    Empty means no queried field changed, which resolves to no subscriber.
    """

    node_ids: list[str]


@dataclass(frozen=True, slots=True)
class ReachedChange:
    """Changed nodes of one related kind, paired with the chain that resolves them to owning roots."""

    node_ids: list[str]
    path: ReachedPath


@dataclass(frozen=True, slots=True)
class RelationshipReachedChanges:
    """Changes that narrow to members, split by how each is mapped back to a group member.

    ``direct_member_node_ids`` already are group members; ``reached`` still needs its relationship
    chain walked back to the owning members. The two resolve independently and their members union.
    """

    direct_member_node_ids: list[str]
    reached: list[ReachedChange]


type ImpactAssessment = EveryTarget | ChangedNodes | RelationshipReachedChanges


@dataclass(frozen=True, kw_only=True, slots=True)
class QueryImpactClassifier:
    """Route a diff onto a query's subscribers from the query's read surface alone.

    Holds what one query analysis established on one branch, so a caller assessing several diffs
    against the same query builds it once. The routing is decided without any id lookup, which
    keeps the rule -- when narrowing is sound and when it is not -- independent of storage.

    Narrowing is sound only when the query pins a single object per root **and** no relevant change
    lands on a kind the query reaches through a relationship. Unique targeting says nothing about
    such a kind, and a node read that way is never tracked as a member of the query's target group,
    so it cannot be mapped back to a subscriber. Those changes widen to every target: over-executing
    is acceptable, leaving a stale output behind is not.

    A kind read both at a root and through a relationship counts as traversed. The two read paths
    are indistinguishable once a change is in hand, so treating it as mappable would narrow away the
    members reached only by the relationship.
    """

    query_branch: str
    only_has_unique_targets: bool
    traversed_kinds: set[str]
    readable_fields_by_kind: dict[str, set[str]]
    reached_paths: dict[str, ReachedPath] = field(default_factory=dict)

    def assess(self, diff_summary: list[NodeDiff]) -> ImpactAssessment:
        if not self.only_has_unique_targets:
            # Any number of objects can answer the query, so a changed node cannot be traced back to
            # the targets reading it.
            any_relevant_change = self._changed_node_ids(diff_summary=diff_summary, kinds=self.readable_fields_by_kind)
            return EveryTarget() if any_relevant_change else ChangedNodes(node_ids=[])

        root_fields_by_kind = {
            kind: fields for kind, fields in self.readable_fields_by_kind.items() if kind not in self.traversed_kinds
        }
        member_node_ids = self._changed_node_ids(diff_summary=diff_summary, kinds=root_fields_by_kind)

        reached: list[ReachedChange] = []
        for kind in sorted(self.traversed_kinds):
            fields = self.readable_fields_by_kind.get(kind)
            if not fields:
                continue
            changed_ids = self._changed_node_ids(diff_summary=diff_summary, kinds={kind: fields})
            if not changed_ids:
                continue
            path = self.reached_paths.get(kind)
            if path is None:
                # A change on this related kind cannot be mapped back to specific members, so every
                # target has to run rather than risk leaving one stale.
                return EveryTarget()
            reached.append(ReachedChange(node_ids=changed_ids, path=path))

        if reached:
            return RelationshipReachedChanges(direct_member_node_ids=member_node_ids, reached=reached)
        return ChangedNodes(node_ids=member_node_ids)

    def _changed_node_ids(self, *, diff_summary: list[NodeDiff], kinds: dict[str, set[str]]) -> list[str]:
        return relevant_node_changes(
            diff_summary=diff_summary, query_branch=self.query_branch, readable_fields_by_kind=kinds
        )
