from dataclasses import dataclass

import pytest

from infrahub.core.constants import HierarchySide
from infrahub.core.schema import NodeSchema
from infrahub.core.validators.node.hierarchy import HierarchyDirection, get_directions_to_check

HIERARCHY = "LocationGeneric"


@dataclass
class DirectionCase:
    name: str
    hierarchy: str | None
    parent: str | None
    children: str | None
    constraint_name: str
    expected: list[HierarchyDirection]


DIRECTION_CASES = [
    DirectionCase(
        name="parent-update-checks-the-parent-side",
        hierarchy=HIERARCHY,
        parent="LocationRegion",
        children="LocationRack",
        constraint_name="node.parent.update",
        expected=[HierarchyDirection(side=HierarchySide.PARENT, peer_kind="LocationRegion")],
    ),
    DirectionCase(
        name="children-update-checks-the-children-side",
        hierarchy=HIERARCHY,
        parent="LocationRegion",
        children="LocationRack",
        constraint_name="node.children.update",
        expected=[HierarchyDirection(side=HierarchySide.CHILDREN, peer_kind="LocationRack")],
    ),
    DirectionCase(
        name="hierarchy-update-checks-both-sides",
        hierarchy=HIERARCHY,
        parent="LocationRegion",
        children="LocationRack",
        constraint_name="node.hierarchy.update",
        expected=[
            HierarchyDirection(side=HierarchySide.PARENT, peer_kind="LocationRegion"),
            HierarchyDirection(side=HierarchySide.CHILDREN, peer_kind="LocationRack"),
        ],
    ),
    DirectionCase(
        name="hierarchical-update-checks-no-side",
        hierarchy=HIERARCHY,
        parent="LocationRegion",
        children="LocationRack",
        constraint_name="node.hierarchical.update",
        expected=[],
    ),
    DirectionCase(
        name="side-without-peer-kind-is-not-checked",
        hierarchy=HIERARCHY,
        parent=None,
        children="LocationRack",
        constraint_name="node.hierarchy.update",
        expected=[HierarchyDirection(side=HierarchySide.CHILDREN, peer_kind="LocationRack")],
    ),
]


@pytest.mark.parametrize("case", DIRECTION_CASES, ids=lambda case: case.name)
def test_directions_to_check(case: DirectionCase) -> None:
    node_schema = NodeSchema(
        name="Site", namespace="Location", hierarchy=case.hierarchy, parent=case.parent, children=case.children
    )

    assert get_directions_to_check(node_schema=node_schema, constraint_name=case.constraint_name) == case.expected
