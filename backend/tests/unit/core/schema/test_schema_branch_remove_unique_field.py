"""Removing an attribute or relationship that is referenced by a uniqueness constraint.

Covers direct updates only (no inheritance). Each test case loads a baseline schema,
then loads an update that removes a field (and optionally adjusts the constraint),
then runs process() and asserts the final state.
"""

from dataclasses import dataclass, field

import pytest

from infrahub.core.constants import (
    HashableModelState,
    RelationshipCardinality,
    RelationshipKind,
)
from infrahub.core.schema import (
    AttributeSchema,
    GenericSchema,
    NodeSchema,
    RelationshipSchema,
    SchemaRoot,
)
from infrahub.core.schema.schema_branch import SchemaBranch


@dataclass
class RemoveFieldTestCase:
    name: str
    initial: SchemaRoot
    update: SchemaRoot
    # kind -> list of attribute names that MUST NOT appear on the schema after process()
    removed_attributes: dict[str, list[str]] = field(default_factory=dict)
    # kind -> list of relationship names that MUST NOT appear on the schema after process()
    removed_relationships: dict[str, list[str]] = field(default_factory=dict)
    # kind -> expected exact uniqueness_constraints value (use None to assert it is unset)
    expected_uniqueness_constraints: dict[str, list[list[str]] | None] = field(default_factory=dict)
    # kind -> expected exact human_friendly_id / display_labels / order_by value (omit a kind to skip the check)
    expected_hfid: dict[str, list[str] | None] = field(default_factory=dict)
    expected_display_labels: dict[str, list[str] | None] = field(default_factory=dict)
    expected_order_by: dict[str, list[str] | None] = field(default_factory=dict)


def _peer_owner() -> NodeSchema:
    return NodeSchema(
        name="Owner",
        namespace="Testing",
        include_in_menu=False,
        attributes=[AttributeSchema(name="name", kind="Text", unique=True)],
    )


def _generic_initial_with_two_attrs_and_two_constraints() -> GenericSchema:
    return GenericSchema(
        name="Sandwich",
        namespace="Testing",
        include_in_menu=False,
        uniqueness_constraints=[["name__value"], ["identifier__value"]],
        human_friendly_id=["name__value", "identifier__value"],
        display_labels=["name__value", "identifier__value"],
        order_by=["name__value", "identifier__value"],
        attributes=[
            AttributeSchema(name="identifier", kind="Number", optional=True),
            AttributeSchema(name="name", kind="Text", optional=True),
        ],
    )


def _generic_initial_with_compound_constraint() -> GenericSchema:
    return GenericSchema(
        name="Sandwich",
        namespace="Testing",
        include_in_menu=False,
        uniqueness_constraints=[["identifier__value", "name__value"]],
        human_friendly_id=["identifier__value", "name__value"],
        display_labels=["identifier__value", "name__value"],
        order_by=["identifier__value", "name__value"],
        attributes=[
            AttributeSchema(name="identifier", kind="Number", optional=True),
            AttributeSchema(name="name", kind="Text", optional=True),
        ],
    )


def _generic_initial_with_rel_in_constraint() -> GenericSchema:
    return GenericSchema(
        name="Sandwich",
        namespace="Testing",
        include_in_menu=False,
        uniqueness_constraints=[["name__value", "owner"]],
        human_friendly_id=["name__value", "owner__name__value"],
        order_by=["name__value", "owner__name__value"],
        attributes=[AttributeSchema(name="name", kind="Text", optional=True)],
        relationships=[
            RelationshipSchema(
                name="owner",
                peer="TestingOwner",
                kind=RelationshipKind.ATTRIBUTE,
                cardinality=RelationshipCardinality.ONE,
                optional=False,
            ),
        ],
    )


def _node_initial_with_two_attrs_and_two_constraints() -> NodeSchema:
    return NodeSchema(
        name="Sandwich",
        namespace="Testing",
        include_in_menu=False,
        uniqueness_constraints=[["name__value"], ["identifier__value"]],
        human_friendly_id=["name__value", "identifier__value"],
        display_labels=["name__value", "identifier__value"],
        order_by=["name__value", "identifier__value"],
        attributes=[
            AttributeSchema(name="identifier", kind="Number", optional=True),
            AttributeSchema(name="name", kind="Text", optional=True),
        ],
    )


def _node_initial_with_compound_constraint() -> NodeSchema:
    return NodeSchema(
        name="Sandwich",
        namespace="Testing",
        include_in_menu=False,
        uniqueness_constraints=[["identifier__value", "name__value"]],
        human_friendly_id=["identifier__value", "name__value"],
        display_labels=["identifier__value", "name__value"],
        order_by=["identifier__value", "name__value"],
        attributes=[
            AttributeSchema(name="identifier", kind="Number", optional=True),
            AttributeSchema(name="name", kind="Text", optional=True),
        ],
    )


def _node_initial_with_rel_in_constraint() -> NodeSchema:
    return NodeSchema(
        name="Sandwich",
        namespace="Testing",
        include_in_menu=False,
        uniqueness_constraints=[["name__value", "owner"]],
        human_friendly_id=["name__value", "owner__name__value"],
        order_by=["name__value", "owner__name__value"],
        attributes=[AttributeSchema(name="name", kind="Text", optional=True)],
        relationships=[
            RelationshipSchema(
                name="owner",
                peer="TestingOwner",
                kind=RelationshipKind.ATTRIBUTE,
                cardinality=RelationshipCardinality.ONE,
                optional=False,
            ),
        ],
    )


def _generic_with_attrs_for_inheritance() -> GenericSchema:
    return GenericSchema(
        name="Sandwich",
        namespace="Testing",
        include_in_menu=False,
        uniqueness_constraints=[["name__value"], ["identifier__value"]],
        human_friendly_id=["name__value", "identifier__value"],
        display_labels=["name__value", "identifier__value"],
        order_by=["name__value", "identifier__value"],
        attributes=[
            AttributeSchema(name="identifier", kind="Number", optional=True),
            AttributeSchema(name="name", kind="Text", optional=True),
        ],
    )


def _generic_with_rel_for_inheritance() -> GenericSchema:
    return GenericSchema(
        name="Sandwich",
        namespace="Testing",
        include_in_menu=False,
        uniqueness_constraints=[["name__value", "owner"]],
        attributes=[AttributeSchema(name="name", kind="Text", optional=True)],
        relationships=[
            RelationshipSchema(
                name="owner",
                peer="TestingOwner",
                kind=RelationshipKind.ATTRIBUTE,
                cardinality=RelationshipCardinality.ONE,
                optional=False,
            ),
        ],
    )


def _inheriting_node() -> NodeSchema:
    return NodeSchema(
        name="CheeseSandwich",
        namespace="Testing",
        include_in_menu=False,
        inherit_from=["TestingSandwich"],
    )


TESTCASES: list[RemoveFieldTestCase] = [
    RemoveFieldTestCase(
        name="generic_remove_attr_strips_from_all_schema_path_properties",
        initial=SchemaRoot(generics=[_generic_initial_with_two_attrs_and_two_constraints()]),
        update=SchemaRoot(
            generics=[
                GenericSchema(
                    name="Sandwich",
                    namespace="Testing",
                    include_in_menu=False,
                    attributes=[
                        AttributeSchema(
                            name="identifier", kind="Number", optional=True, state=HashableModelState.ABSENT
                        ),
                    ],
                ),
            ],
        ),
        removed_attributes={"TestingSandwich": ["identifier"]},
        expected_uniqueness_constraints={"TestingSandwich": [["name__value"]]},
        expected_hfid={"TestingSandwich": ["name__value"]},
        expected_display_labels={"TestingSandwich": ["name__value"]},
        expected_order_by={"TestingSandwich": ["name__value"]},
    ),
    RemoveFieldTestCase(
        name="generic_remove_attr_in_compound_constraint_strips_path",
        initial=SchemaRoot(generics=[_generic_initial_with_compound_constraint()]),
        update=SchemaRoot(
            generics=[
                GenericSchema(
                    name="Sandwich",
                    namespace="Testing",
                    include_in_menu=False,
                    attributes=[
                        AttributeSchema(
                            name="identifier", kind="Number", optional=True, state=HashableModelState.ABSENT
                        ),
                    ],
                ),
            ],
        ),
        removed_attributes={"TestingSandwich": ["identifier"]},
        expected_uniqueness_constraints={"TestingSandwich": [["name__value"]]},
        expected_hfid={"TestingSandwich": ["name__value"]},
        expected_display_labels={"TestingSandwich": ["name__value"]},
        expected_order_by={"TestingSandwich": ["name__value"]},
    ),
    RemoveFieldTestCase(
        name="generic_remove_relationship_in_compound_constraint_strips_path",
        initial=SchemaRoot(generics=[_generic_initial_with_rel_in_constraint()], nodes=[_peer_owner()]),
        update=SchemaRoot(
            generics=[
                GenericSchema(
                    name="Sandwich",
                    namespace="Testing",
                    include_in_menu=False,
                    relationships=[
                        RelationshipSchema(
                            name="owner",
                            peer="TestingOwner",
                            kind=RelationshipKind.ATTRIBUTE,
                            cardinality=RelationshipCardinality.ONE,
                            optional=False,
                            state=HashableModelState.ABSENT,
                        ),
                    ],
                ),
            ],
        ),
        removed_relationships={"TestingSandwich": ["owner"]},
        expected_uniqueness_constraints={"TestingSandwich": [["name__value"]]},
        expected_hfid={"TestingSandwich": ["name__value"]},
        expected_order_by={"TestingSandwich": ["name__value"]},
    ),
    RemoveFieldTestCase(
        name="node_remove_attr_strips_from_all_schema_path_properties",
        initial=SchemaRoot(nodes=[_node_initial_with_two_attrs_and_two_constraints()]),
        update=SchemaRoot(
            nodes=[
                NodeSchema(
                    name="Sandwich",
                    namespace="Testing",
                    include_in_menu=False,
                    attributes=[
                        AttributeSchema(
                            name="identifier", kind="Number", optional=True, state=HashableModelState.ABSENT
                        ),
                    ],
                ),
            ],
        ),
        removed_attributes={"TestingSandwich": ["identifier"]},
        expected_uniqueness_constraints={"TestingSandwich": [["name__value"]]},
        expected_hfid={"TestingSandwich": ["name__value"]},
        expected_display_labels={"TestingSandwich": ["name__value"]},
        expected_order_by={"TestingSandwich": ["name__value"]},
    ),
    RemoveFieldTestCase(
        name="node_remove_attr_in_compound_constraint_strips_path",
        initial=SchemaRoot(nodes=[_node_initial_with_compound_constraint()]),
        update=SchemaRoot(
            nodes=[
                NodeSchema(
                    name="Sandwich",
                    namespace="Testing",
                    include_in_menu=False,
                    attributes=[
                        AttributeSchema(
                            name="identifier", kind="Number", optional=True, state=HashableModelState.ABSENT
                        ),
                    ],
                ),
            ],
        ),
        removed_attributes={"TestingSandwich": ["identifier"]},
        expected_uniqueness_constraints={"TestingSandwich": [["name__value"]]},
        expected_hfid={"TestingSandwich": ["name__value"]},
        expected_display_labels={"TestingSandwich": ["name__value"]},
        expected_order_by={"TestingSandwich": ["name__value"]},
    ),
    RemoveFieldTestCase(
        name="node_remove_relationship_in_compound_constraint_strips_path",
        initial=SchemaRoot(nodes=[_node_initial_with_rel_in_constraint(), _peer_owner()]),
        update=SchemaRoot(
            nodes=[
                NodeSchema(
                    name="Sandwich",
                    namespace="Testing",
                    include_in_menu=False,
                    relationships=[
                        RelationshipSchema(
                            name="owner",
                            peer="TestingOwner",
                            kind=RelationshipKind.ATTRIBUTE,
                            cardinality=RelationshipCardinality.ONE,
                            optional=False,
                            state=HashableModelState.ABSENT,
                        ),
                    ],
                ),
            ],
        ),
        removed_relationships={"TestingSandwich": ["owner"]},
        expected_uniqueness_constraints={"TestingSandwich": [["name__value"]]},
        expected_hfid={"TestingSandwich": ["name__value"]},
        expected_order_by={"TestingSandwich": ["name__value"]},
    ),
    # Inherited deletions — Generic loses a field; Node inherits constraints/attrs from Generic
    RemoveFieldTestCase(
        name="inherited_generic_attr_removed_node_schema_paths_get_reconciled",
        initial=SchemaRoot(generics=[_generic_with_attrs_for_inheritance()], nodes=[_inheriting_node()]),
        update=SchemaRoot(
            generics=[
                GenericSchema(
                    name="Sandwich",
                    namespace="Testing",
                    include_in_menu=False,
                    attributes=[
                        AttributeSchema(
                            name="identifier", kind="Number", optional=True, state=HashableModelState.ABSENT
                        ),
                    ],
                ),
            ],
        ),
        removed_attributes={
            "TestingSandwich": ["identifier"],
            "TestingCheeseSandwich": ["identifier"],
        },
        expected_uniqueness_constraints={
            "TestingSandwich": [["name__value"]],
            "TestingCheeseSandwich": [["name__value"]],
        },
        expected_hfid={
            "TestingSandwich": ["name__value"],
            "TestingCheeseSandwich": ["name__value"],
        },
        expected_display_labels={
            "TestingSandwich": ["name__value"],
            "TestingCheeseSandwich": ["name__value"],
        },
        expected_order_by={
            "TestingSandwich": ["name__value"],
            "TestingCheeseSandwich": ["name__value"],
        },
    ),
    RemoveFieldTestCase(
        name="inherited_generic_relationship_removed_node_constraints_get_reconciled",
        initial=SchemaRoot(generics=[_generic_with_rel_for_inheritance()], nodes=[_peer_owner(), _inheriting_node()]),
        update=SchemaRoot(
            generics=[
                GenericSchema(
                    name="Sandwich",
                    namespace="Testing",
                    include_in_menu=False,
                    relationships=[
                        RelationshipSchema(
                            name="owner",
                            peer="TestingOwner",
                            kind=RelationshipKind.ATTRIBUTE,
                            cardinality=RelationshipCardinality.ONE,
                            optional=False,
                            state=HashableModelState.ABSENT,
                        ),
                    ],
                ),
            ],
        ),
        removed_relationships={
            "TestingSandwich": ["owner"],
            "TestingCheeseSandwich": ["owner"],
        },
        expected_uniqueness_constraints={
            "TestingSandwich": [["name__value"]],
            "TestingCheeseSandwich": [["name__value"]],
        },
    ),
]


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in TESTCASES])
def test_remove_field_referenced_by_uniqueness_constraint(test_case: RemoveFieldTestCase) -> None:
    branch = SchemaBranch(cache={}, name="test")
    branch.load_schema(schema=test_case.initial)
    branch.process(validate_schema=False)
    branch.load_schema(schema=test_case.update)
    branch.process(validate_schema=False)

    for kind, removed in test_case.removed_attributes.items():
        schema = branch.get(name=kind, duplicate=False)
        present_attr_names = {a.name for a in schema.attributes if a.state != HashableModelState.ABSENT}
        for name in removed:
            assert name not in present_attr_names, f"{kind} still has attribute {name!r}: {sorted(present_attr_names)}"

    for kind, removed in test_case.removed_relationships.items():
        schema = branch.get(name=kind, duplicate=False)
        present_rel_names = {r.name for r in schema.relationships if r.state != HashableModelState.ABSENT}
        for name in removed:
            assert name not in present_rel_names, f"{kind} still has relationship {name!r}: {sorted(present_rel_names)}"

    for kind, expected in test_case.expected_uniqueness_constraints.items():
        schema = branch.get(name=kind, duplicate=False)
        assert schema.uniqueness_constraints == expected, (
            f"{kind} uniqueness_constraints {schema.uniqueness_constraints!r} != expected {expected!r}"
        )

    for kind, expected_hfid in test_case.expected_hfid.items():
        schema = branch.get(name=kind, duplicate=False)
        assert schema.human_friendly_id == expected_hfid, (
            f"{kind} human_friendly_id {schema.human_friendly_id!r} != expected {expected_hfid!r}"
        )

    for kind, expected_dl in test_case.expected_display_labels.items():
        schema = branch.get(name=kind, duplicate=False)
        assert schema.display_labels == expected_dl, (
            f"{kind} display_labels {schema.display_labels!r} != expected {expected_dl!r}"
        )

    for kind, expected_ob in test_case.expected_order_by.items():
        schema = branch.get(name=kind, duplicate=False)
        assert schema.order_by == expected_ob, f"{kind} order_by {schema.order_by!r} != expected {expected_ob!r}"
