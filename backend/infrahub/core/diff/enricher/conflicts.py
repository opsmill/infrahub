from uuid import uuid4

from ..model.path import (
    CalculatedDiffs,
    DiffAttribute,
    DiffNode,
    DiffProperty,
    EnrichedDiffAttribute,
    EnrichedDiffNode,
    EnrichedDiffProperty,
    EnrichedDiffPropertyConflict,
    EnrichedDiffRoot,
)
from .interface import DiffEnricherInterface


class DiffConflictsEnricher(DiffEnricherInterface):
    async def enrich(self, enriched_diff_root: EnrichedDiffRoot, calculated_diffs: CalculatedDiffs) -> None:
        base_node_map = {n.uuid: n for n in calculated_diffs.base_branch_diff.nodes}
        branch_node_map = {n.uuid: n for n in calculated_diffs.diff_branch_diff.nodes}
        common_node_uuids = set(base_node_map.keys()) & set(branch_node_map.keys())
        if not common_node_uuids:
            return
        for enriched_node in enriched_diff_root.nodes:
            if enriched_node.uuid not in common_node_uuids:
                continue
            base_node = base_node_map[enriched_node.uuid]
            branch_node = branch_node_map[enriched_node.uuid]
            self._enrich_node(
                enriched_node=enriched_node, base_calculated_node=base_node, branch_calculated_node=branch_node
            )

    def _enrich_node(
        self, enriched_node: EnrichedDiffNode, base_calculated_node: DiffNode, branch_calculated_node: DiffNode
    ) -> None:
        base_attribute_map = {a.name: a for a in base_calculated_node.attributes}
        branch_attribute_map = {a.name: a for a in branch_calculated_node.attributes}
        common_attribute_names = set(base_attribute_map.keys()) & set(branch_attribute_map.keys())
        if not common_attribute_names:
            return
        for enriched_attribute in enriched_node.attributes:
            if enriched_attribute.name not in common_attribute_names:
                continue
            base_attribute = base_attribute_map[enriched_attribute.name]
            branch_attribute = branch_attribute_map[enriched_attribute.name]
            self._enrich_attribute(
                enriched_attribute=enriched_attribute,
                base_calculated_attribute=base_attribute,
                branch_calculated_attribute=branch_attribute,
            )

    def _enrich_attribute(
        self,
        enriched_attribute: EnrichedDiffAttribute,
        base_calculated_attribute: DiffAttribute,
        branch_calculated_attribute: DiffAttribute,
    ) -> None:
        base_property_map = {p.property_type: p for p in base_calculated_attribute.properties}
        branch_property_map = {p.property_type: p for p in branch_calculated_attribute.properties}
        common_property_types = set(base_property_map.keys()) & set(branch_property_map.keys())
        if not common_property_types:
            return
        for enriched_property in enriched_attribute.properties:
            if enriched_property.property_type not in common_property_types:
                continue
            base_property = base_property_map[enriched_property.property_type]
            branch_property = branch_property_map[enriched_property.property_type]
            self._add_property_conflict(
                enriched_property=enriched_property,
                base_calculated_property=base_property,
                branch_calculated_property=branch_property,
            )

    def _add_property_conflict(
        self,
        enriched_property: EnrichedDiffProperty,
        base_calculated_property: DiffProperty,
        branch_calculated_property: DiffProperty,
    ) -> None:
        if base_calculated_property.new_value == branch_calculated_property.new_value:
            return
        enriched_property.conflict = EnrichedDiffPropertyConflict(
            uuid=str(uuid4()),
            base_branch_action=base_calculated_property.action,
            base_branch_value=base_calculated_property.new_value,
            base_branch_changed_at=base_calculated_property.changed_at,
            diff_branch_action=branch_calculated_property.action,
            diff_branch_value=branch_calculated_property.new_value,
            diff_branch_changed_at=branch_calculated_property.changed_at,
            selected_branch=None,
        )
