from infrahub.core.constants.database import DatabaseEdgeType
from infrahub.core.diff.enricher.path_identifier import DiffPathIdentifierEnricher
from infrahub.core.diff.model.diff import ModifiedPathType

from .factories import (
    EnrichedAttributeFactory,
    EnrichedNodeFactory,
    EnrichedPropertyFactory,
    EnrichedRelationshipElementFactory,
    EnrichedRelationshipGroupFactory,
    EnrichedRootFactory,
)


class TestPathIdentifierEnricher:
    async def test_path_identifiers_added(self):
        diff_attribute_value_property = EnrichedPropertyFactory.build(property_type=DatabaseEdgeType.HAS_VALUE)
        diff_attribute_property = EnrichedPropertyFactory.build(property_type=DatabaseEdgeType.HAS_OWNER)
        diff_attribute = EnrichedAttributeFactory.build(
            properties={diff_attribute_property, diff_attribute_value_property}
        )
        diff_relationship_value_property = EnrichedPropertyFactory.build(property_type=DatabaseEdgeType.HAS_VALUE)
        diff_relationship_property = EnrichedPropertyFactory.build(property_type=DatabaseEdgeType.IS_PROTECTED)
        diff_relationship_element = EnrichedRelationshipElementFactory.build(
            properties={diff_relationship_property, diff_relationship_value_property}
        )
        diff_relationship = EnrichedRelationshipGroupFactory.build(relationships={diff_relationship_element})
        diff_node = EnrichedNodeFactory.build(relationships={diff_relationship}, attributes={diff_attribute})
        diff_root = EnrichedRootFactory.build(nodes={diff_node})
        enricher = DiffPathIdentifierEnricher()

        await enricher.enrich(enriched_diff_root=diff_root, calculated_diffs=None)

        enriched_node = diff_root.nodes.pop()
        node_path = f"{ModifiedPathType.DATA.value}/{diff_node.uuid}"
        assert enriched_node.path_identifier == node_path
        enriched_attribute = enriched_node.attributes.pop()
        attribute_path = f"{node_path}/{diff_attribute.name}"
        assert enriched_attribute.path_identifier == attribute_path
        attribute_property_paths = {p.path_identifier for p in enriched_attribute.properties}
        assert attribute_property_paths == {
            f"{attribute_path}/value",
            f"{attribute_path}/property/{DatabaseEdgeType.HAS_OWNER.value}",
        }
        enriched_relationship = enriched_node.relationships.pop()
        relationship_path = f"{node_path}/{enriched_relationship.name}"
        assert enriched_relationship.path_identifier == relationship_path
        enriched_element = enriched_relationship.relationships.pop()
        element_path = f"{relationship_path}/{enriched_element.peer_id}"
        assert enriched_element.path_identifier == element_path
        element_property_paths = {p.path_identifier for p in enriched_element.properties}
        assert element_property_paths == {
            f"{element_path}/value",
            f"{element_path}/property/{DatabaseEdgeType.IS_PROTECTED.value}",
        }
