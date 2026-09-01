from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from .predicates import relevant_node_changes

if TYPE_CHECKING:
    from infrahub_sdk.diff import NodeDiff


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


type ImpactAssessment = EveryTarget | ChangedNodes


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

    ``depends_on_everything`` marks a query whose read surface cannot be pinned down at all -- a read
    of a derived value composed from a peer the read set never names -- so any relevant change widens
    to every target.
    """

    query_branch: str
    only_has_unique_targets: bool
    traversed_kinds: set[str]
    readable_fields_by_kind: dict[str, set[str]]
    depends_on_everything: bool = False

    def assess(self, diff_summary: list[NodeDiff]) -> ImpactAssessment:
        changed_node_ids = self._changed_node_ids(diff_summary=diff_summary, kinds=self.readable_fields_by_kind)
        if self._must_widen(diff_summary=diff_summary, changed_node_ids=changed_node_ids):
            return EveryTarget()

        return ChangedNodes(node_ids=changed_node_ids)

    def _must_widen(self, *, diff_summary: list[NodeDiff], changed_node_ids: list[str]) -> bool:
        if self.depends_on_everything or not self.only_has_unique_targets:
            # A changed node cannot be traced back to the targets reading it: the query answers from
            # an unbounded set, or reads a derived value moved by a peer the read set cannot name.
            return bool(changed_node_ids)

        traversed_fields_by_kind = {
            kind: fields for kind, fields in self.readable_fields_by_kind.items() if kind in self.traversed_kinds
        }
        return bool(self._changed_node_ids(diff_summary=diff_summary, kinds=traversed_fields_by_kind))

    def _changed_node_ids(self, *, diff_summary: list[NodeDiff], kinds: dict[str, set[str]]) -> list[str]:
        return relevant_node_changes(
            diff_summary=diff_summary, query_branch=self.query_branch, readable_fields_by_kind=kinds
        )
