from __future__ import annotations

from dataclasses import dataclass

import pytest

from infrahub.core.branch import Branch
from infrahub.core.constants import RelationshipCardinality
from infrahub.core.node import Node
from infrahub.core.schema import AttributeSchema, NodeSchema, RelationshipSchema
from infrahub.core.timestamp import Timestamp


def _node(display_label: str | None, human_friendly_id: list[str] | None) -> Node:
    schema = NodeSchema(
        name="Shirt",
        namespace="Test",
        display_label=display_label,
        human_friendly_id=human_friendly_id,
        attributes=[AttributeSchema(name="name", kind="Text")],
        relationships=[
            RelationshipSchema(name="color", peer="TestColor", cardinality=RelationshipCardinality.ONE, optional=True),
            RelationshipSchema(name="brand", peer="TestBrand", cardinality=RelationshipCardinality.ONE, optional=False),
            RelationshipSchema(name="tags", peer="BuiltinTag", cardinality=RelationshipCardinality.MANY, optional=True),
        ],
    )
    return Node(schema=schema, branch=Branch(name="main"), at=Timestamp())


@dataclass
class NeedsReadCase:
    name: str
    display_label: str | None
    human_friendly_id: list[str] | None
    display_label_needs_read: bool
    hfid_needs_read: bool


NEEDS_READ_CASES = [
    NeedsReadCase(
        name="both_labels_defined_without_stored_values",
        display_label="{{ name__value }}",
        human_friendly_id=["name__value"],
        display_label_needs_read=True,
        hfid_needs_read=True,
    ),
    NeedsReadCase(
        name="display_label_only",
        display_label="name__value",
        human_friendly_id=None,
        display_label_needs_read=True,
        hfid_needs_read=False,
    ),
    NeedsReadCase(
        name="hfid_only",
        display_label=None,
        human_friendly_id=["name__value"],
        display_label_needs_read=False,
        hfid_needs_read=True,
    ),
    NeedsReadCase(
        name="no_labels_defined",
        display_label=None,
        human_friendly_id=None,
        display_label_needs_read=False,
        hfid_needs_read=False,
    ),
]


@pytest.mark.parametrize("case", NEEDS_READ_CASES, ids=lambda case: case.name)
def test_label_needs_read_follows_the_labels_the_schema_defines(case: NeedsReadCase) -> None:
    """A node that holds no stored label computes the ones its schema defines, and none other."""
    node = _node(display_label=case.display_label, human_friendly_id=case.human_friendly_id)

    assert node.display_label_needs_read() is case.display_label_needs_read
    assert node.hfid_needs_read() is case.hfid_needs_read
