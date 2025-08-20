from collections import Counter
from typing import Iterable

from infrahub.core.constants import DiffAction

from ..model.path import (
    BaseSummary,
    CalculatedDiffs,
    EnrichedDiffAttribute,
    EnrichedDiffNode,
    EnrichedDiffRelationship,
    EnrichedDiffRoot,
    EnrichedDiffSingleRelationship,
)
from .interface import DiffEnricherInterface


class DiffSummaryCountsEnricher(DiffEnricherInterface):
    async def enrich(
        self,
        enriched_diff_root: EnrichedDiffRoot,
        calculated_diffs: CalculatedDiffs | None = None,  # noqa: ARG002
    ) -> None:
        self._add_root_summaries(diff_root=enriched_diff_root)

    def _add_summary(self, summary_node: BaseSummary, actions: Iterable[DiffAction]) -> None:
        summary_count = Counter(actions)
        summary_node.num_added = summary_count.get(DiffAction.ADDED, 0)
        summary_node.num_updated = summary_count.get(DiffAction.UPDATED, 0)
        summary_node.num_removed = summary_count.get(DiffAction.REMOVED, 0)

    def _add_root_summaries(self, diff_root: EnrichedDiffRoot) -> None:
        contains_conflict = False
        num_conflicts = 0
        for diff_node in diff_root.nodes:
            contains_conflict |= self._add_node_summaries(diff_node=diff_node)
            if diff_node.conflict or diff_node.contains_conflict:
                num_conflicts += 1
        self._add_summary(summary_node=diff_root, actions=(n.action for n in diff_root.nodes))
        diff_root.contains_conflict = contains_conflict
        diff_root.num_conflicts = num_conflicts
        self._add_child_nodes_to_summaries(diff_root=diff_root)

    def _add_node_summaries(self, diff_node: EnrichedDiffNode) -> bool:
        contains_conflict = False
        num_conflicts = 0
        for diff_attr in diff_node.attributes:
            contains_conflict |= self._add_attribute_summaries(diff_attribute=diff_attr)
            if diff_attr.contains_conflict:
                num_conflicts += 1
        for diff_rel in diff_node.relationships:
            contains_conflict |= self._add_relationship_summaries(diff_relationship=diff_rel)
            if diff_rel.contains_conflict:
                num_conflicts += 1
        self._add_summary(
            summary_node=diff_node, actions=(field.action for field in diff_node.relationships | diff_node.attributes)
        )
        diff_node.contains_conflict = contains_conflict
        diff_node.num_conflicts = num_conflicts
        return contains_conflict

    def _add_attribute_summaries(self, diff_attribute: EnrichedDiffAttribute) -> bool:
        contains_conflict = False
        num_conflicts = 0
        for diff_prop in diff_attribute.properties:
            if diff_prop.conflict:
                num_conflicts += 1
                contains_conflict = True
        self._add_summary(summary_node=diff_attribute, actions=(p.action for p in diff_attribute.properties))
        diff_attribute.contains_conflict = contains_conflict
        diff_attribute.num_conflicts = num_conflicts
        return contains_conflict

    def _add_relationship_summaries(self, diff_relationship: EnrichedDiffRelationship) -> bool:
        contains_conflict = False
        num_conflicts = 0
        for diff_element in diff_relationship.relationships:
            contains_conflict |= self._add_element_summaries(diff_element=diff_element)
            if diff_element.conflict:
                num_conflicts += 1
        self._add_summary(summary_node=diff_relationship, actions=(e.action for e in diff_relationship.relationships))
        diff_relationship.contains_conflict = contains_conflict
        diff_relationship.num_conflicts = num_conflicts
        return contains_conflict

    def _add_element_summaries(self, diff_element: EnrichedDiffSingleRelationship) -> bool:
        if diff_element.conflict is None:
            contains_conflict = False
            num_conflicts = 0
        else:
            contains_conflict = True
            num_conflicts = 1
        for diff_prop in diff_element.properties:
            if diff_prop.conflict:
                num_conflicts += 1
                contains_conflict = True
        self._add_summary(summary_node=diff_element, actions=(p.action for p in diff_element.properties))
        diff_element.contains_conflict = contains_conflict
        diff_element.num_conflicts = num_conflicts
        return contains_conflict

    def _add_child_nodes_to_summaries(self, diff_root: EnrichedDiffRoot) -> None:
        for diff_node in diff_root.nodes:
            for diff_rel in diff_node.relationships:
                if not diff_rel.contains_conflict:
                    diff_rel.contains_conflict = any(n.contains_conflict for n in diff_rel.nodes)
                diff_rel.num_conflicts += sum(bool(n.contains_conflict or n.conflict) for n in diff_rel.nodes)
