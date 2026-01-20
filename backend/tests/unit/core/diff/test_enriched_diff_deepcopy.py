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


class TestEnrichedDiffRelationshipDeepCopy:
    """Test deepcopy behavior with circular references in EnrichedDiffRelationship.

    The data model has a recursive structure:
    - EnrichedDiffRelationship.nodes -> set[EnrichedDiffNode]
    - EnrichedDiffNode.relationships -> set[EnrichedDiffRelationship]

    Custom __deepcopy__ methods handle this by:
    1. Creating a new instance and setting hashable attributes first
    2. Registering in memo before copying complex attributes
    3. Then copying complex attributes that may have circular references
    """

    def test_deepcopy_relationship_with_circular_node_reference(self) -> None:
        """Test deepcopy works with circular references starting from a relationship.

        Creates: relationship.nodes -> node.relationships -> relationship
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

        # This would fail without the custom __deepcopy__ methods
        copied = deepcopy(relationship)

        assert copied.name == relationship.name
        assert copied is not relationship
        assert len(copied.nodes) == 1
        # Verify the circular structure is preserved
        copied_node = next(iter(copied.nodes))
        assert copied_node is not node
        assert len(copied_node.relationships) == 1
        assert next(iter(copied_node.relationships)) is copied

    def test_deepcopy_node_with_circular_relationship_reference(self) -> None:
        """Test deepcopy works with circular references starting from a node."""
        relationship = EnrichedRelationshipGroupFactory.build(
            name="circular_rel",
            action=DiffAction.UPDATED,
            cardinality=RelationshipCardinality.ONE,
            relationships={EnrichedRelationshipElementFactory.build()},
            nodes=set(),
        )

        node = EnrichedNodeFactory.build(
            action=DiffAction.UPDATED,
            attributes=set(),
            relationships={relationship},
        )

        # Create circular reference
        relationship.nodes.add(node)

        # This would fail without the custom __deepcopy__ methods
        copied_node = deepcopy(node)

        assert copied_node is not node
        assert len(copied_node.relationships) == 1
        copied_rel = next(iter(copied_node.relationships))
        assert copied_rel.name == relationship.name
        # Verify the circular structure is preserved
        assert len(copied_rel.nodes) == 1
        assert next(iter(copied_rel.nodes)) is copied_node
