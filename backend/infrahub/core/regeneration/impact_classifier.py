from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from .models import ImpactScope
from .predicates import relevant_node_changes

if TYPE_CHECKING:
    from infrahub_sdk.diff import NodeDiff


@dataclass(frozen=True, kw_only=True, slots=True)
class ImpactAssessment:
    """How a diff routes, plus the changed nodes a narrowed routing still has to resolve.

    ``changed_node_ids`` is meaningful only for ``ImpactScope.SPECIFIC``, where the caller maps
    those nodes to the subscribers tracking them. The other scopes need no id resolution.
    """

    scope: ImpactScope
    changed_node_ids: list[str] = field(default_factory=list)


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

        if self.only_has_unique_targets:
            related_fields_by_kind = {
                kind: fields for kind, fields in self.readable_fields_by_kind.items() if kind not in self.root_kinds
            }
            if self._changed_node_ids(diff_summary=diff_summary, kinds=related_fields_by_kind):
                return ImpactAssessment(scope=ImpactScope.ALL)

            return ImpactAssessment(scope=ImpactScope.SPECIFIC, changed_node_ids=changed_node_ids)

        if changed_node_ids:
            return ImpactAssessment(scope=ImpactScope.ALL)

        return ImpactAssessment(scope=ImpactScope.NONE)

    def _changed_node_ids(self, *, diff_summary: list[NodeDiff], kinds: dict[str, set[str]]) -> list[str]:
        return relevant_node_changes(
            diff_summary=diff_summary, query_branch=self.query_branch, readable_fields_by_kind=kinds
        )
