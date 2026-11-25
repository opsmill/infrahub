from dataclasses import dataclass
from typing import Any

import pytest

from infrahub.core.constants import HierarchySide
from infrahub.core.schema import NodeSchema, SchemaRoot
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.core.validators.node.hierarchy import (
    HierarchyDirection,
    get_directions_to_check,
    get_kinds_left_in_hierarchy,
)

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
    DirectionCase(
        name="empty-peer-kind-is-checked-as-no-allowed-peer",
        hierarchy=HIERARCHY,
        parent="",
        children="",
        constraint_name="node.hierarchy.update",
        expected=[
            HierarchyDirection(side=HierarchySide.PARENT, peer_kind=""),
            HierarchyDirection(side=HierarchySide.CHILDREN, peer_kind=""),
        ],
    ),
    DirectionCase(
        name="kind-outside-a-hierarchy-checks-no-side",
        hierarchy=None,
        parent="",
        children="",
        constraint_name="node.hierarchy.update",
        expected=[],
    ),
]


@pytest.mark.parametrize("case", DIRECTION_CASES, ids=lambda case: case.name)
def test_directions_to_check(case: DirectionCase) -> None:
    node_schema = NodeSchema(
        name="Site", namespace="Location", hierarchy=case.hierarchy, parent=case.parent, children=case.children
    )

    assert get_directions_to_check(node_schema=node_schema, constraint_name=case.constraint_name) == case.expected


def _location_root(hierarchical: bool, kinds: list[str], removed_kinds: list[str]) -> SchemaRoot:
    generic: dict[str, Any] = {
        "name": "Generic",
        "namespace": "Location",
        "hierarchical": hierarchical,
        "attributes": [{"name": "name", "kind": "Text"}],
    }
    # The ids make the kinds existing ones, which a removal marks absent instead of dropping.
    nodes = [
        {
            "id": f"id-{kind}",
            "name": kind,
            "namespace": "Location",
            "inherit_from": [HIERARCHY],
            "state": "absent" if kind in removed_kinds else "present",
        }
        for kind in kinds
    ]
    return SchemaRoot(version="1.0", generics=[generic], nodes=nodes)


@dataclass
class KindsLeftCase:
    name: str
    current_hierarchical: bool
    candidate_hierarchical: bool
    kinds: list[str]
    removed_kinds: list[str]
    expected: list[str]


KINDS_LEFT_CASES = [
    KindsLeftCase(
        name="leaving-a-used-hierarchy-lists-its-kinds-sorted",
        current_hierarchical=True,
        candidate_hierarchical=False,
        kinds=["Site", "Region"],
        removed_kinds=[],
        expected=["LocationRegion", "LocationSite"],
    ),
    KindsLeftCase(
        name="leaving-an-unused-hierarchy",
        current_hierarchical=True,
        candidate_hierarchical=False,
        kinds=[],
        removed_kinds=[],
        expected=[],
    ),
    KindsLeftCase(
        name="staying-hierarchical",
        current_hierarchical=True,
        candidate_hierarchical=True,
        kinds=["Site", "Region"],
        removed_kinds=[],
        expected=[],
    ),
    KindsLeftCase(
        name="becoming-hierarchical",
        current_hierarchical=False,
        candidate_hierarchical=True,
        kinds=["Site", "Region"],
        removed_kinds=[],
        expected=[],
    ),
    KindsLeftCase(
        name="never-hierarchical",
        current_hierarchical=False,
        candidate_hierarchical=False,
        kinds=["Site", "Region"],
        removed_kinds=[],
        expected=[],
    ),
    KindsLeftCase(
        name="leaving-a-hierarchy-while-removing-its-kinds",
        current_hierarchical=True,
        candidate_hierarchical=False,
        kinds=["Site", "Region"],
        removed_kinds=["Site", "Region"],
        expected=[],
    ),
]


@pytest.mark.parametrize("case", KINDS_LEFT_CASES, ids=lambda case: case.name)
def test_kinds_left_in_hierarchy(case: KindsLeftCase) -> None:
    current = SchemaBranch(cache={}, name="test")
    current.load_schema(
        schema=_location_root(hierarchical=case.current_hierarchical, kinds=case.kinds, removed_kinds=[])
    )
    current.process()
    candidate = current.duplicate()
    candidate.load_schema(
        schema=_location_root(
            hierarchical=case.candidate_hierarchical, kinds=case.kinds, removed_kinds=case.removed_kinds
        )
    )
    candidate.process()

    assert (
        get_kinds_left_in_hierarchy(
            current=current.get_generic(name=HIERARCHY),
            candidate=candidate.get_generic(name=HIERARCHY),
            schema_branch=candidate,
        )
        == case.expected
    )
