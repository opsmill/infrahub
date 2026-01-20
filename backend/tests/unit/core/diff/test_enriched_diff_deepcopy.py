"""Tests for deepcopy behavior of EnrichedDiff model classes.

These tests verify that deepcopy works correctly with circular references
between EnrichedDiffRelationship and EnrichedDiffNode.

The fix: Custom __deepcopy__ methods on EnrichedDiffRelationship and EnrichedDiffNode
ensure that hashable attributes (name, identifier) are set before the instance is
registered in the memo dict, preventing AttributeError when __hash__ is called
during circular reference handling.

Related code: DiffCombiner._combine_relationships calls deepcopy() on
EnrichedDiffRelationship objects that may have circular node references.
"""

from copy import deepcopy

from tests.component.core.diff.factories import (
    EnrichedNodeFactory,
    EnrichedRelationshipElementFactory,
    EnrichedRelationshipGroupFactory,
)

from infrahub.core.constants import DiffAction, RelationshipCardinality


def test_deepcopy_diff_with_circular_reference() -> None:
    """Test deepcopy behavior with circular references in EnrichedDiffRelationship.

    The data model has a recursive structure:
    - EnrichedDiffRelationship.nodes -> set[EnrichedDiffNode]
    - EnrichedDiffNode.relationships -> set[EnrichedDiffRelationship]

    using deepcopy() on an object with a recersive reference to a `set` of its own class could fail
    depending on the order in which attributes are handled in deepcopy(). custom __deepcopy__ methods
    ensure the attributes are set in the correct order
    """
    # Create a relationship with a node in its nodes set
    relationship = EnrichedRelationshipGroupFactory.build(
        name="parent_relationship",
        action=DiffAction.ADDED,
        cardinality=RelationshipCardinality.MANY,
        relationships={EnrichedRelationshipElementFactory.build(action=DiffAction.ADDED)},
        nodes=set(),
    )

    # Create a node that references this relationship
    node = EnrichedNodeFactory.build(
        action=DiffAction.ADDED,
        attributes=set(),
        relationships={relationship},
    )

    # Create the circular reference: relationship.nodes contains the node
    # which has relationship in its relationships set
    relationship.nodes.add(node)

    # validate copying the relationship works
    copied = deepcopy(relationship)
    assert copied.name == relationship.name
    assert copied is not relationship
    assert len(copied.nodes) == 1
    copied_node = next(iter(copied.nodes))
    assert copied_node is not node
    assert copied_node.identifier == node.identifier
    assert len(copied_node.relationships) == 1
    assert next(iter(copied_node.relationships)) is copied

    # validate copying the node works
    copied_node = deepcopy(node)
    assert copied_node.identifier == node.identifier
    assert copied_node is not node
    assert len(copied_node.relationships) == 1
    copied_rel = next(iter(copied_node.relationships))
    assert copied_rel.name == relationship.name
    assert len(copied_rel.nodes) == 1
    assert next(iter(copied_rel.nodes)) is copied_node
