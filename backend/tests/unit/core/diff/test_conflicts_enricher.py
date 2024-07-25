import pytest

from infrahub.core.diff.enricher.conflicts import DiffConflictsEnricher

from .factories import (
    CalculatedDiffsFactory,
    DiffAttributeFactory,
    DiffNodeFactory,
    DiffPropertyFactory,
    DiffRootFactory,
    EnrichedAttributeFactory,
    EnrichedNodeFactory,
    EnrichedPropertyFactory,
    EnrichedRootFactory,
)


class TestConflictsEnricher:
    @pytest.fixture
    def conflicts_enricher(self) -> DiffConflictsEnricher:
        return DiffConflictsEnricher()

    async def test_attribute_conflicts_both_changed_to_same_value(self, conflicts_enricher: DiffConflictsEnricher):
        new_value = "NEW"
        enriched_property = EnrichedPropertyFactory.build(new_value=new_value)
        base_property = DiffPropertyFactory.build(
            property_type=enriched_property.property_type, previous_value="SOMETHING", new_value=new_value
        )
        branch_property = DiffPropertyFactory.build(
            property_type=enriched_property.property_type, previous_value="ELSE", new_value=new_value
        )
        enriched_attribute = EnrichedAttributeFactory.build(properties={enriched_property})
        base_attribute = DiffAttributeFactory.build(name=enriched_attribute.name, properties=[base_property])
        branch_attribute = DiffAttributeFactory.build(name=enriched_attribute.name, properties=[branch_property])
        enriched_node = EnrichedNodeFactory.build(attributes={enriched_attribute}, relationships=set())
        base_node = DiffNodeFactory.build(uuid=enriched_node.uuid, attributes=[base_attribute])
        branch_node = DiffNodeFactory.build(uuid=enriched_node.uuid, attributes=[branch_attribute])
        enriched_root = EnrichedRootFactory.build(nodes={enriched_node})
        base_root = DiffRootFactory.build(nodes=[base_node])
        branch_root = DiffRootFactory.build(nodes=[branch_node])
        calculated_diffs = CalculatedDiffsFactory.build(base_branch_diff=base_root, diff_branch_diff=branch_root)

        await conflicts_enricher.enrich(enriched_diff_root=enriched_root, calculated_diffs=calculated_diffs)

        for node in enriched_root.nodes:
            for attribute in node.attributes:
                for prop in attribute.properties:
                    assert prop.conflict is None
