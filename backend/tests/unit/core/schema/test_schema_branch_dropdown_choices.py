"""Removing dropdown choices by loading a schema update that marks them ``state: absent``."""

import pytest

from infrahub.core.constants import HashableModelState
from infrahub.core.schema import AttributeSchema, DropdownChoice, GenericSchema, NodeSchema, SchemaRoot
from infrahub.core.schema.schema_branch import SchemaBranch

ABSENT = HashableModelState.ABSENT


def _resource(choices: list[DropdownChoice] | None = None, *, with_criticality: bool = True) -> GenericSchema:
    attributes = [AttributeSchema(name="name", kind="Text", unique=True)]
    if with_criticality:
        attributes.append(AttributeSchema(name="criticality", kind="Dropdown", optional=True, choices=choices))
    return GenericSchema(name="Resource", namespace="Testing", include_in_menu=False, attributes=attributes)


def _server() -> NodeSchema:
    return NodeSchema(
        name="Server",
        namespace="Testing",
        include_in_menu=False,
        inherit_from=["TestingResource"],
        attributes=[AttributeSchema(name="model", kind="Text", optional=True)],
    )


def _three_tiers() -> list[DropdownChoice]:
    return [DropdownChoice(name="tier_1"), DropdownChoice(name="tier_2"), DropdownChoice(name="tier_3")]


def _criticality_choices(schema_branch: SchemaBranch, kind: str) -> list[str]:
    choices = schema_branch.get(name=kind, duplicate=False).get_attribute(name="criticality").choices
    assert choices is not None
    return sorted(choice.name for choice in choices)


def _loaded_branch(initial: SchemaRoot) -> SchemaBranch:
    schema_branch = SchemaBranch(cache={}, name="test")
    schema_branch.load_schema(schema=initial)
    schema_branch.process()
    return schema_branch


def test_absent_choice_is_removed_from_the_generic_and_every_inheriting_node() -> None:
    schema_branch = _loaded_branch(SchemaRoot(version="1.0", generics=[_resource(_three_tiers())], nodes=[_server()]))
    assert _criticality_choices(schema_branch, "TestingServer") == ["tier_1", "tier_2", "tier_3"]

    # The update lists only the removed choice: the merge keeps every stored choice the file leaves out.
    update = SchemaRoot(version="1.0", generics=[_resource([DropdownChoice(name="tier_2", state=ABSENT)])])
    schema_branch.load_schema(schema=update)
    schema_branch.process()

    assert _criticality_choices(schema_branch, "TestingResource") == ["tier_1", "tier_3"]
    assert _criticality_choices(schema_branch, "TestingServer") == ["tier_1", "tier_3"]


def test_update_removing_every_choice_is_rejected() -> None:
    schema_branch = _loaded_branch(SchemaRoot(version="1.0", generics=[_resource(_three_tiers())], nodes=[_server()]))

    every_choice_absent = [DropdownChoice(name=choice.name, state=ABSENT) for choice in _three_tiers()]
    schema_branch.load_schema(schema=SchemaRoot(version="1.0", generics=[_resource(every_choice_absent)]))

    with pytest.raises(
        ValueError, match=r"^Unable to remove the last dropdown on TestingResource in attribute criticality$"
    ):
        schema_branch.process()


def test_absent_choice_on_a_new_attribute_is_not_stored() -> None:
    schema_branch = _loaded_branch(
        SchemaRoot(version="1.0", generics=[_resource(with_criticality=False)], nodes=[_server()])
    )

    choices = [DropdownChoice(name="tier_1"), DropdownChoice(name="tier_2", state=ABSENT)]
    schema_branch.load_schema(schema=SchemaRoot(version="1.0", generics=[_resource(choices)]))
    schema_branch.process()

    assert _criticality_choices(schema_branch, "TestingResource") == ["tier_1"]
    assert _criticality_choices(schema_branch, "TestingServer") == ["tier_1"]


def test_absent_choice_on_a_new_node_is_not_stored() -> None:
    choices = [DropdownChoice(name="tier_1"), DropdownChoice(name="tier_2", state=ABSENT)]
    schema_branch = _loaded_branch(SchemaRoot(version="1.0", generics=[_resource(choices)], nodes=[_server()]))

    assert _criticality_choices(schema_branch, "TestingResource") == ["tier_1"]
    assert _criticality_choices(schema_branch, "TestingServer") == ["tier_1"]
