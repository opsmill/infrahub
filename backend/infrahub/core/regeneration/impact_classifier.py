from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from .predicates import relevant_node_changes

if TYPE_CHECKING:
    from infrahub_sdk.diff import NodeDiff


@dataclass(frozen=True, slots=True)
class EveryTarget:
    """The changed nodes cannot be traced back to specific targets, so every one must be processed.

    The alternative to an enumerated set rather than one more member of it: the affected targets
    are unknown here, not known-and-listed.
    """


@dataclass(frozen=True, slots=True)
class ChangedNodes:
    """These changed nodes map onto group members, so their subscribers can be resolved.

    Empty means no queried field changed, which resolves to no subscriber.
    """

    node_ids: list[str]


type ImpactAssessment = EveryTarget | ChangedNodes


@dataclass(frozen=True, kw_only=True, slots=True)
class QueryImpactClassifier:
    """Route a diff onto a query's subscribers from the query's read surface alone.

    Holds what one query analysis established on one branch, so a caller assessing several diffs
    against the same query builds it once. The routing is decided without any id lookup, which
    keeps the rule -- when narrowing is sound and when it is not -- independent of storage.

    Narrowing is sound only when the query pins a single object per root **and** every relevant
    change lands on a kind the query reads at that root. Unique targeting says nothing about kinds
    reached by traversing a relationship, and such a node is never tracked as a member of the
    query's target group, so it cannot be mapped back to a subscriber. Those changes widen to every
    target: over-executing is acceptable, leaving a stale output behind is not.
    """

    query_branch: str
    only_has_unique_targets: bool
    root_kinds: set[str]
    readable_fields_by_kind: dict[str, set[str]]

    def assess(self, diff_summary: list[NodeDiff]) -> ImpactAssessment:
        changed_node_ids = self._changed_node_ids(diff_summary=diff_summary, kinds=self.readable_fields_by_kind)
        if self._must_widen(diff_summary=diff_summary, changed_node_ids=changed_node_ids):
            return EveryTarget()

        return ChangedNodes(node_ids=changed_node_ids)

    def _must_widen(self, *, diff_summary: list[NodeDiff], changed_node_ids: list[str]) -> bool:
        if not self.only_has_unique_targets:
            # Any number of objects can answer the query, so a changed node cannot be traced back to
            # the targets reading it.
            return bool(changed_node_ids)

        related_fields_by_kind = {
            kind: fields for kind, fields in self.readable_fields_by_kind.items() if kind not in self.root_kinds
        }
        return bool(self._changed_node_ids(diff_summary=diff_summary, kinds=related_fields_by_kind))

    def _changed_node_ids(self, *, diff_summary: list[NodeDiff], kinds: dict[str, set[str]]) -> list[str]:
        return relevant_node_changes(
            diff_summary=diff_summary, query_branch=self.query_branch, readable_fields_by_kind=kinds
        )
