from typing import TYPE_CHECKING, Any

from infrahub.core.constants import NULL_VALUE, DiffAction, RelationshipCardinality
from infrahub.core.constants.database import DatabaseEdgeType
from infrahub.database import InfrahubDatabase
from infrahub.log import get_logger

from ..model.path import (
    CalculatedDiffs,
    EnrichedDiffProperty,
    EnrichedDiffRelationship,
    EnrichedDiffRoot,
    EnrichedDiffSingleRelationship,
)
from .interface import DiffEnricherInterface

if TYPE_CHECKING:
    from infrahub.core.schema import MainSchemaTypes

log = get_logger()


class DiffCardinalityOneEnricher(DiffEnricherInterface):
    """Clean up diffs for cardinality=one relationships to make them cleaner and more intuitive

    Final result is that each EnrichedDiffRelationship for a relationship of cardinality one
     - MUST have a single EnrichedDiffSingleRelationship (we'll call it the element)
     - the peer_id property of the element will be the latest non-null peer ID for this element
     - the element MUST have an EnrichedDiffProperty of property_type=IS_RELATED that correctly records
        the previous and new values of the peer ID for this element
     - changes to properties (IS_VISIBLE, etc) of a cardinality=one relationship are consolidated as well
    """

    def __init__(self, db: InfrahubDatabase):
        self.db = db
        self._node_schema_map: dict[str, MainSchemaTypes] = {}

    async def enrich(self, enriched_diff_root: EnrichedDiffRoot, calculated_diffs: CalculatedDiffs) -> None:  # noqa: ARG002
        self._node_schema_map = {}
        log.info("Beginning cardinality-one diff enrichment...")
        for diff_node in enriched_diff_root.nodes:
            for relationship_group in diff_node.relationships:
                if (
                    relationship_group.cardinality is RelationshipCardinality.ONE
                    and len(relationship_group.relationships) > 0
                ):
                    self.consolidate_cardinality_one_diff_elements(diff_relationship=relationship_group)
        log.info("Cardinality-one diff enrichment complete.")

    def _determine_action(self, previous_value: Any, new_value: Any) -> DiffAction:
        if previous_value == new_value:
            return DiffAction.UNCHANGED
        if previous_value in (None, NULL_VALUE):
            return DiffAction.ADDED
        if new_value in (None, NULL_VALUE):
            return DiffAction.REMOVED
        return DiffAction.UPDATED

    def _build_property_maps(
        self, diff_relationship: EnrichedDiffRelationship
    ) -> tuple[dict[DatabaseEdgeType, EnrichedDiffProperty], dict[DatabaseEdgeType, EnrichedDiffProperty]]:
        earliest_property_map: dict[DatabaseEdgeType, EnrichedDiffProperty] = {}
        latest_property_map: dict[DatabaseEdgeType, EnrichedDiffProperty] = {}
        for diff_rel_element in diff_relationship.relationships:
            for diff_property in diff_rel_element.properties:
                prop_type = diff_property.property_type
                current_earliest = earliest_property_map.get(prop_type)
                if not current_earliest:
                    earliest_property_map[prop_type] = diff_property
                elif diff_property.changed_at < current_earliest.changed_at:
                    earliest_property_map[prop_type] = diff_property
                # special handling for a REMOVE and ADD with the same timestamp to treat them as an update
                elif diff_property.changed_at == current_earliest.changed_at:
                    if diff_property.action is DiffAction.REMOVED and current_earliest.action is DiffAction.ADDED:
                        earliest_property_map[prop_type] = diff_property

                current_latest = latest_property_map.get(prop_type)
                if not current_latest:
                    latest_property_map[prop_type] = diff_property
                elif diff_property.changed_at > current_latest.changed_at:
                    latest_property_map[prop_type] = diff_property
                # special handling for a REMOVE and ADD with the same timestamp to treat them as an update
                elif diff_property.changed_at == current_latest.changed_at:
                    if diff_property.action is DiffAction.ADDED and current_latest.action is DiffAction.REMOVED:
                        latest_property_map[prop_type] = diff_property
        return (earliest_property_map, latest_property_map)

    def consolidate_cardinality_one_diff_elements(self, diff_relationship: EnrichedDiffRelationship) -> None:
        earliest_property_map, latest_property_map = self._build_property_maps(diff_relationship=diff_relationship)
        consolidated_properties = set()
        for prop_type, earliest_prop in earliest_property_map.items():
            latest_prop = latest_property_map[prop_type]
            # this means there was only one property of this type, so we keep it
            if earliest_prop is latest_prop:
                consolidated_properties.add(latest_prop)
                continue
            prop_action = self._determine_action(
                previous_value=earliest_prop.previous_value, new_value=latest_prop.new_value
            )
            consolidated_properties.add(
                EnrichedDiffProperty(
                    property_type=prop_type,
                    changed_at=latest_prop.changed_at,
                    previous_value=earliest_prop.previous_value,
                    new_value=latest_prop.new_value,
                    action=prop_action,
                    conflict=None,
                )
            )
        if consolidated_properties:
            element_actions = {element.action for element in diff_relationship.relationships}
            # check if this is a simultaneous update
            if len(diff_relationship.relationships) > 1 and {DiffAction.REMOVED, DiffAction.ADDED} <= element_actions:
                latest_element = [
                    element for element in diff_relationship.relationships if element.action is DiffAction.ADDED
                ][0]
                consolidated_element_action = DiffAction.UPDATED
            else:
                latest_element = max(diff_relationship.relationships, key=lambda elem: elem.changed_at)
                consolidated_element_action = latest_element.action
            diff_relationship.relationships = {
                EnrichedDiffSingleRelationship(
                    changed_at=latest_element.changed_at,
                    action=consolidated_element_action,
                    peer_id=latest_element.peer_id,
                    peer_label=latest_element.peer_label,
                    conflict=None,
                    properties=consolidated_properties,
                )
            }
