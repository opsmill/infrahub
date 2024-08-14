from collections import Counter
from typing import Iterable

from infrahub.core.branch import Branch
from infrahub.core.constants import DiffAction
from infrahub.core.timestamp import Timestamp

from .calculator import DiffCalculator
from .combiner import DiffCombiner
from .conflicts_enricher import ConflictsEnricher
from .enricher.aggregated import AggregatedDiffEnricher
from .model.path import (
    BaseSummary,
    EnrichedDiffAttribute,
    EnrichedDiffNode,
    EnrichedDiffRelationship,
    EnrichedDiffRoot,
    EnrichedDiffSingleRelationship,
    TimeRange,
)
from .repository.repository import DiffRepository


class DiffCoordinator:
    def __init__(
        self,
        diff_repo: DiffRepository,
        diff_calculator: DiffCalculator,
        diff_enricher: AggregatedDiffEnricher,
        diff_combiner: DiffCombiner,
        conflicts_enricher: ConflictsEnricher,
    ) -> None:
        self.diff_repo = diff_repo
        self.diff_calculator = diff_calculator
        self.diff_enricher = diff_enricher
        self.diff_combiner = diff_combiner
        self.conflicts_enricher = conflicts_enricher

    async def update_diffs(
        self,
        base_branch: Branch,
        diff_branch: Branch,
        from_time: Timestamp,
        to_time: Timestamp,
    ) -> None:
        enriched_branch_diffs = await self.diff_repo.get(
            base_branch_name=base_branch.name,
            diff_branch_names=[diff_branch.name],
            from_time=from_time,
            to_time=to_time,
        )
        enriched_base_diffs = await self.diff_repo.get(
            base_branch_name=base_branch.name,
            diff_branch_names=[base_branch.name],
            from_time=from_time,
            to_time=to_time,
        )
        covered_time_ranges = [
            TimeRange(from_time=enriched_diff.from_time, to_time=enriched_diff.to_time)
            for enriched_diff in enriched_branch_diffs
        ]
        missing_time_ranges = self._get_missing_time_ranges(
            time_ranges=covered_time_ranges, from_time=from_time, to_time=to_time
        )
        for missing_time_range in missing_time_ranges:
            calculated_diff_pair = await self.diff_calculator.calculate_diff(
                base_branch=base_branch,
                diff_branch=diff_branch,
                from_time=missing_time_range.from_time,
                to_time=missing_time_range.to_time,
            )
            enriched_diff_pair = await self.diff_enricher.enrich(calculated_diffs=calculated_diff_pair)
            enriched_branch_diffs.append(enriched_diff_pair.diff_branch_diff)
            enriched_base_diffs.append(enriched_diff_pair.base_branch_diff)

        enriched_branch_diffs.sort(key=lambda e_diff: e_diff.from_time)
        combined_branch_diff = enriched_branch_diffs[0]
        for next_diff in enriched_branch_diffs[1:]:
            combined_branch_diff = await self.diff_combiner.combine(
                earlier_diff=combined_branch_diff, later_diff=next_diff
            )
        enriched_base_diffs.sort(key=lambda e_diff: e_diff.from_time)
        combined_base_diff = enriched_base_diffs[0]
        for next_diff in enriched_base_diffs[1:]:
            combined_base_diff = await self.diff_combiner.combine(earlier_diff=combined_base_diff, later_diff=next_diff)

        await self.conflicts_enricher.add_conflicts_to_branch_diff(
            base_diff_root=combined_base_diff, branch_diff_root=combined_branch_diff
        )
        self._add_root_summaries(diff_root=combined_base_diff)
        self._add_root_summaries(diff_root=combined_branch_diff)
        await self.diff_repo.save(enriched_diff=combined_base_diff)
        await self.diff_repo.save(enriched_diff=combined_branch_diff)

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
        contains_conflict = False
        num_conflicts = 0
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

    def _get_missing_time_ranges(
        self, time_ranges: list[TimeRange], from_time: Timestamp, to_time: Timestamp
    ) -> list[TimeRange]:
        if not time_ranges:
            return [TimeRange(from_time=from_time, to_time=to_time)]
        missing_time_ranges = []
        if time_ranges[0].from_time > from_time:
            missing_time_ranges.append(TimeRange(from_time=from_time, to_time=time_ranges[0].from_time))
        index = 0
        while index < len(time_ranges) - 1:
            this_diff = time_ranges[index]
            next_diff = time_ranges[index + 1]
            if this_diff.to_time != next_diff.from_time:
                missing_time_ranges.append(TimeRange(from_time=this_diff.to_time, to_time=next_diff.from_time))
            index += 1
        if time_ranges[-1].to_time < to_time:
            missing_time_ranges.append(TimeRange(from_time=time_ranges[-1].to_time, to_time=to_time))
        return missing_time_ranges
