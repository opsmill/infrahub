from dataclasses import dataclass
from typing import Any

import pytest

from infrahub.core.constants import HierarchySide
from infrahub.core.schema import AttributeSchema, GenericSchema, NodeSchema, RelationshipSchema, SchemaRoot
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.core.validators.node.hierarchy import (
    HierarchyDirection,
    HierarchyFieldConflict,
    get_directions_to_check,
    get_generic_hierarchy_conflicts,
    get_hierarchy_field_conflicts,
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


def _relationship(name: str, peer: str, inherited: bool = False) -> RelationshipSchema:
    return RelationshipSchema(name=name, peer=peer, cardinality="one", optional=True, inherited=inherited)


def _site(
    hierarchy: str | None = None,
    attributes: list[AttributeSchema] | None = None,
    relationships: list[RelationshipSchema] | None = None,
) -> NodeSchema:
    return NodeSchema(
        name="Site",
        namespace="Location",
        hierarchy=hierarchy,
        attributes=attributes or [],
        relationships=relationships or [],
    )


@dataclass
class ConflictCase:
    name: str
    current: NodeSchema | None
    candidate: NodeSchema
    expected: list[HierarchyFieldConflict]


CONFLICT_CASES = [
    ConflictCase(
        name="own-parent-relationship",
        current=_site(relationships=[_relationship(name="parent", peer="OrganizationTenant")]),
        candidate=_site(hierarchy=HIERARCHY),
        expected=[HierarchyFieldConflict(field_name="parent", value="OrganizationTenant")],
    ),
    ConflictCase(
        name="own-children-relationship",
        current=_site(relationships=[_relationship(name="children", peer="OrganizationTenant")]),
        candidate=_site(hierarchy=HIERARCHY),
        expected=[HierarchyFieldConflict(field_name="children", value="OrganizationTenant")],
    ),
    ConflictCase(
        name="own-parent-and-children-relationships",
        current=_site(
            relationships=[
                _relationship(name="parent", peer="OrganizationTenant"),
                _relationship(name="children", peer="OrganizationSite"),
            ]
        ),
        candidate=_site(hierarchy=HIERARCHY),
        expected=[
            HierarchyFieldConflict(field_name="parent", value="OrganizationTenant"),
            HierarchyFieldConflict(field_name="children", value="OrganizationSite"),
        ],
    ),
    ConflictCase(
        name="inherited-parent-relationship",
        current=_site(relationships=[_relationship(name="parent", peer=HIERARCHY, inherited=True)]),
        candidate=_site(hierarchy=HIERARCHY),
        expected=[],
    ),
    ConflictCase(
        name="no-parent-or-children-relationship",
        current=_site(relationships=[_relationship(name="owner", peer="OrganizationTenant")]),
        candidate=_site(hierarchy=HIERARCHY),
        expected=[],
    ),
    ConflictCase(
        name="new-kind",
        current=None,
        candidate=_site(hierarchy=HIERARCHY),
        expected=[],
    ),
    ConflictCase(
        name="kind-already-in-a-hierarchy",
        current=_site(hierarchy=HIERARCHY, relationships=[_relationship(name="parent", peer="OrganizationTenant")]),
        candidate=_site(hierarchy=HIERARCHY),
        expected=[],
    ),
    ConflictCase(
        name="kind-not-joining-a-hierarchy",
        current=_site(relationships=[_relationship(name="parent", peer="OrganizationTenant")]),
        candidate=_site(),
        expected=[],
    ),
    ConflictCase(
        name="reserved-attribute-name",
        current=_site(),
        candidate=_site(hierarchy=HIERARCHY, attributes=[AttributeSchema(name="ancestors", kind="Text")]),
        expected=[HierarchyFieldConflict(field_name="ancestors", value="Text")],
    ),
    ConflictCase(
        name="reserved-relationship-name",
        current=_site(),
        candidate=_site(
            hierarchy=HIERARCHY, relationships=[_relationship(name="descendants", peer="OrganizationTenant")]
        ),
        expected=[HierarchyFieldConflict(field_name="descendants", value="OrganizationTenant")],
    ),
    ConflictCase(
        name="inherited-reserved-attribute-name",
        current=_site(),
        candidate=_site(
            hierarchy=HIERARCHY, attributes=[AttributeSchema(name="ancestors", kind="Text", inherited=True)]
        ),
        expected=[],
    ),
]


@pytest.mark.parametrize("case", CONFLICT_CASES, ids=lambda case: case.name)
def test_hierarchy_field_conflicts(case: ConflictCase) -> None:
    assert get_hierarchy_field_conflicts(current=case.current, candidate=case.candidate) == case.expected


def _generic(
    hierarchical: bool,
    attributes: list[AttributeSchema] | None = None,
    relationships: list[RelationshipSchema] | None = None,
    used_by: list[str] | None = None,
) -> GenericSchema:
    return GenericSchema(
        name="Generic",
        namespace="Location",
        hierarchical=hierarchical,
        attributes=attributes or [],
        relationships=relationships or [],
        used_by=used_by or [],
    )


def _schema_branch_with_kinds_in_hierarchy(kinds: list[str]) -> SchemaBranch:
    schema_branch = SchemaBranch(cache={}, name="test")
    for kind in kinds:
        schema_branch.set(
            name=f"Location{kind}", schema=NodeSchema(name=kind, namespace="Location", hierarchy=HIERARCHY)
        )
    return schema_branch


@dataclass
class GenericConflictCase:
    name: str
    current: GenericSchema
    candidate: GenericSchema
    kinds_in_hierarchy: list[str]
    expected: list[HierarchyFieldConflict]


GENERIC_CONFLICT_CASES = [
    GenericConflictCase(
        name="becoming-hierarchical-with-a-reserved-attribute-name",
        current=_generic(hierarchical=False, attributes=[AttributeSchema(name="ancestors", kind="Text")]),
        candidate=_generic(hierarchical=True, attributes=[AttributeSchema(name="ancestors", kind="Text")]),
        kinds_in_hierarchy=[],
        expected=[HierarchyFieldConflict(field_name="ancestors", value="Text")],
    ),
    GenericConflictCase(
        name="becoming-hierarchical-with-a-reserved-relationship-name",
        current=_generic(hierarchical=False),
        candidate=_generic(
            hierarchical=True, relationships=[_relationship(name="descendants", peer="OrganizationTenant")]
        ),
        kinds_in_hierarchy=[],
        expected=[HierarchyFieldConflict(field_name="descendants", value="OrganizationTenant")],
    ),
    GenericConflictCase(
        name="becoming-hierarchical-with-its-own-parent-relationship",
        current=_generic(hierarchical=False, relationships=[_relationship(name="parent", peer="OrganizationTenant")]),
        candidate=_generic(hierarchical=True, relationships=[_relationship(name="parent", peer="OrganizationTenant")]),
        kinds_in_hierarchy=[],
        expected=[HierarchyFieldConflict(field_name="parent", value="OrganizationTenant")],
    ),
    GenericConflictCase(
        name="becoming-hierarchical-with-its-own-children-relationship",
        current=_generic(hierarchical=False, relationships=[_relationship(name="children", peer="OrganizationSite")]),
        candidate=_generic(hierarchical=True, relationships=[_relationship(name="children", peer="OrganizationSite")]),
        kinds_in_hierarchy=[],
        expected=[HierarchyFieldConflict(field_name="children", value="OrganizationSite")],
    ),
    GenericConflictCase(
        name="becoming-hierarchical-with-the-hierarchy-parent-relationship",
        current=_generic(hierarchical=False),
        candidate=_generic(hierarchical=True, relationships=[_relationship(name="parent", peer=HIERARCHY)]),
        kinds_in_hierarchy=[],
        expected=[],
    ),
    GenericConflictCase(
        name="becoming-hierarchical-without-a-reserved-name",
        current=_generic(hierarchical=False, attributes=[AttributeSchema(name="name", kind="Text")]),
        candidate=_generic(hierarchical=True, attributes=[AttributeSchema(name="name", kind="Text")]),
        kinds_in_hierarchy=[],
        expected=[],
    ),
    GenericConflictCase(
        name="leaving-a-used-hierarchy",
        current=_generic(hierarchical=True, used_by=["LocationSite"]),
        candidate=_generic(hierarchical=False, used_by=["LocationSite"]),
        kinds_in_hierarchy=["Site"],
        expected=[HierarchyFieldConflict(field_name="hierarchical", value=["LocationSite"])],
    ),
    GenericConflictCase(
        name="leaving-an-unused-hierarchy-with-a-reserved-name",
        current=_generic(hierarchical=True, attributes=[AttributeSchema(name="ancestors", kind="Text")]),
        candidate=_generic(hierarchical=False, attributes=[AttributeSchema(name="ancestors", kind="Text")]),
        kinds_in_hierarchy=[],
        expected=[],
    ),
    GenericConflictCase(
        name="staying-hierarchical-with-a-reserved-name",
        current=_generic(hierarchical=True, attributes=[AttributeSchema(name="ancestors", kind="Text")]),
        candidate=_generic(hierarchical=True, attributes=[AttributeSchema(name="ancestors", kind="Text")]),
        kinds_in_hierarchy=[],
        expected=[],
    ),
    GenericConflictCase(
        name="never-hierarchical-with-a-reserved-name",
        current=_generic(hierarchical=False, attributes=[AttributeSchema(name="ancestors", kind="Text")]),
        candidate=_generic(hierarchical=False, attributes=[AttributeSchema(name="ancestors", kind="Text")]),
        kinds_in_hierarchy=[],
        expected=[],
    ),
]


@pytest.mark.parametrize("case", GENERIC_CONFLICT_CASES, ids=lambda case: case.name)
def test_generic_hierarchy_conflicts(case: GenericConflictCase) -> None:
    schema_branch = _schema_branch_with_kinds_in_hierarchy(kinds=case.kinds_in_hierarchy)

    assert (
        get_generic_hierarchy_conflicts(current=case.current, candidate=case.candidate, schema_branch=schema_branch)
        == case.expected
    )
