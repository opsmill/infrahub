"""Relaxing an attribute from unique=True to unique=False on an already-processed schema.

Each case loads a baseline schema where an attribute is unique (but not referenced by the
human_friendly_id), runs process() so the derived single-attribute uniqueness constraint is
materialised, then loads an update that sets the attribute to unique=False without restating
uniqueness_constraints, and runs process() again. The relaxation must stick: the flag must be
False and the derived `[attr__value]` constraint must be gone. A second unique attribute that
backs the HFID is left untouched as a control.
"""

from dataclasses import dataclass

import pytest

from infrahub.core.schema import (
    AttributeSchema,
    GenericSchema,
    NodeSchema,
    SchemaRoot,
)
from infrahub.core.schema.schema_branch import SchemaBranch


def _generic_with_unique_serial() -> GenericSchema:
    return GenericSchema(
        name="Sandwich",
        namespace="Testing",
        include_in_menu=False,
        human_friendly_id=["name__value"],
        attributes=[
            AttributeSchema(name="name", kind="Text", unique=True),
            AttributeSchema(name="serial", kind="Text", unique=True, optional=True),
        ],
    )


def _node_with_unique_serial() -> NodeSchema:
    return NodeSchema(
        name="Sandwich",
        namespace="Testing",
        include_in_menu=False,
        human_friendly_id=["name__value"],
        attributes=[
            AttributeSchema(name="name", kind="Text", unique=True),
            AttributeSchema(name="serial", kind="Text", unique=True, optional=True),
        ],
    )


def _inheriting_node() -> NodeSchema:
    return NodeSchema(
        name="CheeseSandwich",
        namespace="Testing",
        include_in_menu=False,
        inherit_from=["TestingSandwich"],
    )


def _relax_serial_generic() -> GenericSchema:
    return GenericSchema(
        name="Sandwich",
        namespace="Testing",
        include_in_menu=False,
        attributes=[AttributeSchema(name="serial", kind="Text", unique=False, optional=True)],
    )


def _relax_serial_node() -> NodeSchema:
    return NodeSchema(
        name="Sandwich",
        namespace="Testing",
        include_in_menu=False,
        attributes=[AttributeSchema(name="serial", kind="Text", unique=False, optional=True)],
    )


@dataclass
class RelaxUniqueTestCase:
    name: str
    initial: SchemaRoot
    update: SchemaRoot
    # Every kind whose `serial` attribute must end up relaxed after the update.
    kinds_to_check: list[str]


TESTCASES: list[RelaxUniqueTestCase] = [
    RelaxUniqueTestCase(
        name="generic_relax_unique_drops_derived_constraint",
        initial=SchemaRoot(generics=[_generic_with_unique_serial()]),
        update=SchemaRoot(generics=[_relax_serial_generic()]),
        kinds_to_check=["TestingSandwich"],
    ),
    RelaxUniqueTestCase(
        name="node_relax_unique_drops_derived_constraint",
        initial=SchemaRoot(nodes=[_node_with_unique_serial()]),
        update=SchemaRoot(nodes=[_relax_serial_node()]),
        kinds_to_check=["TestingSandwich"],
    ),
    RelaxUniqueTestCase(
        name="inherited_node_relax_unique_on_generic_drops_derived_constraint",
        initial=SchemaRoot(generics=[_generic_with_unique_serial()], nodes=[_inheriting_node()]),
        update=SchemaRoot(generics=[_relax_serial_generic()]),
        kinds_to_check=["TestingSandwich", "TestingCheeseSandwich"],
    ),
]


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in TESTCASES])
def test_relax_unique_attribute_sticks(test_case: RelaxUniqueTestCase) -> None:
    branch = SchemaBranch(cache={}, name="test")
    branch.load_schema(schema=test_case.initial)
    branch.process(validate_schema=False)
    branch.load_schema(schema=test_case.update)
    branch.process(validate_schema=False)

    for kind in test_case.kinds_to_check:
        schema = branch.get(name=kind, duplicate=False)

        serial = schema.get_attribute(name="serial")
        assert serial.unique is False, f"{kind}.serial.unique was re-derived to True after relaxation"

        constraints = schema.uniqueness_constraints or []
        assert ["serial__value"] not in constraints, (
            f"{kind} still carries the derived [serial__value] constraint: {constraints!r}"
        )

        # Control: the HFID-backed attribute is untouched and stays unique.
        name_attr = schema.get_attribute(name="name")
        assert name_attr.unique is True, f"{kind}.name.unique was unexpectedly changed"
        assert ["name__value"] in constraints, f"{kind} lost the [name__value] constraint: {constraints!r}"
