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
    """Changed nodes of one related kind, paired with the chains that resolve them to owning roots.

    The kind may be reached by more than one relationship chain; the changed nodes are mapped back
    through every one and the resolved owners are unioned.
    """

    node_ids: list[str]
    paths: tuple[ReachedPath, ...]


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

    Narrowing needs the query to pin a single object per root. A relevant change on a root kind then
    maps straight to its members. A relevant change on a kind reached through a relationship maps
    back only when every relationship chain down to that kind has been reconstructed: the members
    are recovered by walking those chains in reverse. When a reached kind has no reconstructed chain,
    that change widens to every target -- over-executing is acceptable, leaving a stale output behind
    is not.

    A kind read both at a root and through a relationship counts as traversed. The two read paths
    are indistinguishable once a change is in hand, so treating it as a plain root change would
    narrow away the members reached only by the relationship.
    """

    query_branch: str
    only_has_unique_targets: bool
    traversed_kinds: set[str]
    readable_fields_by_kind: dict[str, set[str]]
    reached_paths: dict[str, tuple[ReachedPath, ...]] = field(default_factory=dict)

    def assess(self, diff_summary: list[NodeDiff]) -> ImpactAssessment:
        if not self.only_has_unique_targets:
            # Any number of objects can answer the query, so a changed node cannot be traced back to
            # the targets reading it.
            has_relevant_change = bool(
                self._changed_node_ids(diff_summary=diff_summary, kinds=self.readable_fields_by_kind)
            )
            return EveryTarget() if has_relevant_change else ChangedNodes(node_ids=[])

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
            paths = self.reached_paths.get(kind)
            if paths is None:
                # A change on this related kind cannot be mapped back to specific members, so every
                # target has to run rather than risk leaving one stale.
                return EveryTarget()
            reached.append(ReachedChange(node_ids=changed_ids, paths=paths))

        if reached:
            return RelationshipReachedChanges(direct_member_node_ids=member_node_ids, reached=reached)
        return ChangedNodes(node_ids=member_node_ids)

    def _changed_node_ids(self, *, diff_summary: list[NodeDiff], kinds: dict[str, set[str]]) -> list[str]:
        return relevant_node_changes(
            diff_summary=diff_summary, query_branch=self.query_branch, readable_fields_by_kind=kinds
        )
