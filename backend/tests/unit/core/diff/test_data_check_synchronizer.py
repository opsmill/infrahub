from __future__ import annotations

import time
from dataclasses import replace

from infrahub.core.constants.database import DatabaseEdgeType
from infrahub.core.diff.data_check_synchronizer import DiffDataCheckSynchronizer
from infrahub.core.diff.model.path import NodeIdentifier
from tests.helpers.diff_factories import (
    EnrichedAttributeFactory,
    EnrichedConflictFactory,
    EnrichedNodeFactory,
    EnrichedPropertyFactory,
    EnrichedRelationshipElementFactory,
    EnrichedRelationshipGroupFactory,
    EnrichedRootFactory,
    NodeIdentifierFactory,
)


def test_nodes_missing_from_the_retrieved_diff_are_added() -> None:
    updated_nodes = {EnrichedNodeFactory.build(attributes=set(), relationships=set()) for _ in range(3)}
    updated_diff = EnrichedRootFactory.build(nodes=updated_nodes)
    retrieved_diff = EnrichedRootFactory.build(nodes=set())

    DiffDataCheckSynchronizer._update_diff_conflicts(updated_diff=updated_diff, retrieved_diff=retrieved_diff)

    assert retrieved_diff.nodes == updated_nodes


def test_conflicts_of_matching_nodes_are_copied_and_missing_fields_added() -> None:
    identifier = NodeIdentifierFactory.build()
    retrieved_property = EnrichedPropertyFactory.build(property_type=DatabaseEdgeType.HAS_VALUE, conflict=None)
    retrieved_attribute = EnrichedAttributeFactory.build(name="name", properties={retrieved_property})
    retrieved_element_property = EnrichedPropertyFactory.build(property_type=DatabaseEdgeType.HAS_OWNER, conflict=None)
    retrieved_element = EnrichedRelationshipElementFactory.build(
        peer_id="peer-1", properties={retrieved_element_property}, conflict=None
    )
    retrieved_relationship = EnrichedRelationshipGroupFactory.build(
        name="peers", relationships={retrieved_element}, nodes=set()
    )
    retrieved_node = EnrichedNodeFactory.build(
        identifier=identifier, attributes={retrieved_attribute}, relationships={retrieved_relationship}, conflict=None
    )
    retrieved_diff = EnrichedRootFactory.build(nodes={retrieved_node})

    node_conflict = EnrichedConflictFactory.build()
    updated_property = EnrichedPropertyFactory.build(
        property_type=DatabaseEdgeType.HAS_VALUE, conflict=EnrichedConflictFactory.build()
    )
    new_property = EnrichedPropertyFactory.build(
        property_type=DatabaseEdgeType.HAS_SOURCE, conflict=EnrichedConflictFactory.build()
    )
    updated_attribute = EnrichedAttributeFactory.build(name="name", properties={updated_property, new_property})
    new_attribute = EnrichedAttributeFactory.build(name="description", properties=set())
    updated_element_property = EnrichedPropertyFactory.build(
        property_type=DatabaseEdgeType.HAS_OWNER, conflict=EnrichedConflictFactory.build()
    )
    updated_element = EnrichedRelationshipElementFactory.build(
        peer_id="peer-1", properties={updated_element_property}, conflict=EnrichedConflictFactory.build()
    )
    new_element = EnrichedRelationshipElementFactory.build(peer_id="peer-2", properties=set(), conflict=None)
    updated_relationship = EnrichedRelationshipGroupFactory.build(
        name="peers", relationships={updated_element, new_element}, nodes=set()
    )
    new_relationship = EnrichedRelationshipGroupFactory.build(name="tags", relationships=set(), nodes=set())
    updated_node = EnrichedNodeFactory.build(
        identifier=identifier,
        attributes={updated_attribute, new_attribute},
        relationships={updated_relationship, new_relationship},
        conflict=node_conflict,
    )
    updated_diff = EnrichedRootFactory.build(nodes={updated_node})

    DiffDataCheckSynchronizer._update_diff_conflicts(updated_diff=updated_diff, retrieved_diff=retrieved_diff)

    assert retrieved_diff.nodes == {retrieved_node}
    assert retrieved_node.conflict is node_conflict
    assert retrieved_property.conflict is updated_property.conflict
    assert retrieved_attribute.get_property(property_type=DatabaseEdgeType.HAS_SOURCE) is new_property
    assert retrieved_node.get_attribute(name="description") is new_attribute
    assert retrieved_element.conflict is updated_element.conflict
    assert retrieved_element_property.conflict is updated_element_property.conflict
    assert retrieved_relationship.get_element(peer_id="peer-2") is new_element
    assert retrieved_node.get_relationship(name="tags") is new_relationship


def test_two_updated_nodes_with_the_same_identifier_fold_into_one_retrieved_node() -> None:
    """Which duplicate is processed first depends on set order, so only order-independent facts are asserted."""
    identifier = NodeIdentifierFactory.build()
    first_conflict = EnrichedConflictFactory.build()
    second_conflict = EnrichedConflictFactory.build()
    attribute_only_on_second = EnrichedAttributeFactory.build(name="description", properties=set())
    first = EnrichedNodeFactory.build(
        identifier=identifier, attributes=set(), relationships=set(), conflict=first_conflict
    )
    second = EnrichedNodeFactory.build(
        identifier=identifier, attributes={attribute_only_on_second}, relationships=set(), conflict=second_conflict
    )
    updated_diff = EnrichedRootFactory.build(nodes={first, second})
    retrieved_diff = EnrichedRootFactory.build(nodes=set())

    DiffDataCheckSynchronizer._update_diff_conflicts(updated_diff=updated_diff, retrieved_diff=retrieved_diff)

    assert len(updated_diff.nodes) == 2
    assert len(retrieved_diff.nodes) == 1
    merged_node = next(iter(retrieved_diff.nodes))
    assert merged_node.identifier == identifier
    # Whichever node came second was folded into the other rather than added or dropped: the attribute
    # only it carried is present, and the surviving conflict is one of the two, not lost.
    assert merged_node.get_attribute(name="description") is attribute_only_on_second
    assert merged_node.conflict is first_conflict or merged_node.conflict is second_conflict


def test_merging_a_large_diff_does_not_scale_quadratically() -> None:
    """A per-node scan of the growing retrieved set took minutes at tens of thousands of nodes."""
    template = EnrichedNodeFactory.build(attributes=set(), relationships=set(), conflict=None)
    updated_nodes = {
        replace(template, identifier=NodeIdentifier(uuid=f"uuid-{index}", kind="InterfacePhysical", db_id=str(index)))
        for index in range(20_000)
    }
    updated_diff = EnrichedRootFactory.build(nodes=updated_nodes)
    retrieved_diff = EnrichedRootFactory.build(nodes=set())

    started_at = time.monotonic()
    DiffDataCheckSynchronizer._update_diff_conflicts(updated_diff=updated_diff, retrieved_diff=retrieved_diff)
    elapsed_seconds = time.monotonic() - started_at

    assert len(retrieved_diff.nodes) == 20_000
    # The quadratic version needs well over 20 s for this many nodes; the linear one a fraction of a second.
    assert elapsed_seconds < 5
