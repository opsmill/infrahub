"""The schema a merge or rebase produces, built from the source branch's own changes only."""

from __future__ import annotations

import pytest

from infrahub.core.constants import RelationshipCardinality
from infrahub.core.merge.schema_builder import MergedSchemaBuilder
from infrahub.core.schema import AttributeSchema, GenericSchema, NodeSchema, RelationshipSchema
from infrahub.core.schema.attribute_parameters import TextAttributeParameters
from infrahub.core.schema.schema_branch import SchemaBranch

CAR_KIND = "TestCar"
TRUCK_KIND = "TestTruck"
CODE_ATTR_ID = "attr-code"
COLOR_ATTR_ID = "attr-color"
CAR_NODE_ID = "node-car"
OWNER_REL_ID = "rel-owner"
PERSON_KIND = "TestPerson"

PERMISSIVE = r".*"
UPPERCASE_ONLY = r"^[A-Z]+$"
LOWERCASE_ONLY = r"^[a-z]+$"


def _car_schema(
    code_regex: str | None = None,
    code_optional: bool = True,
    color_regex: str | None = None,
    uniqueness_constraints: list[list[str]] | None = None,
    extra_attribute: str | None = None,
) -> NodeSchema:
    attributes = [
        AttributeSchema(
            id=CODE_ATTR_ID,
            name="code",
            kind="Text",
            optional=code_optional,
            parameters=TextAttributeParameters(regex=code_regex),
        ),
        AttributeSchema(
            id=COLOR_ATTR_ID,
            name="color",
            kind="Text",
            optional=True,
            parameters=TextAttributeParameters(regex=color_regex),
        ),
    ]
    if extra_attribute:
        attributes.append(AttributeSchema(name=extra_attribute, kind="Text", optional=True))
    return NodeSchema(
        id=CAR_NODE_ID,
        name="Car",
        namespace="Test",
        attributes=attributes,
        relationships=[
            RelationshipSchema(
                id=OWNER_REL_ID,
                name="owner",
                peer=PERSON_KIND,
                identifier="car__person",
                cardinality=RelationshipCardinality.ONE,
                optional=True,
            )
        ],
        uniqueness_constraints=uniqueness_constraints,
    )


def _branch(name: str, car: NodeSchema, process: bool = False) -> SchemaBranch:
    return _named_branch(name=name, kind=CAR_KIND, car=car, process=process)


def _renamed_kind_branch(name: str, process: bool = False) -> SchemaBranch:
    """The car schema with its kind renamed, keeping the id so the diff reports a rename."""
    renamed = _car_schema()
    renamed.name = "Vehicle"
    return _named_branch(name=name, kind="TestVehicle", car=renamed, process=process)


def _inheriting_branch(name: str, inherited_name: str) -> SchemaBranch:
    """A car inheriting one attribute from a generic, so the attribute has no id of its own."""
    branch = SchemaBranch(cache={}, name=name)
    branch.set(
        name="TestThing",
        schema=GenericSchema(
            id="gen-thing",
            name="Thing",
            namespace="Test",
            attributes=[AttributeSchema(id="attr-source", name=inherited_name, kind="Text", optional=True)],
        ),
    )
    branch.set(
        name=CAR_KIND,
        schema=NodeSchema(
            id=CAR_NODE_ID,
            name="Car",
            namespace="Test",
            inherit_from=["TestThing"],
            attributes=[AttributeSchema(id=COLOR_ATTR_ID, name="color", kind="Text", optional=True)],
        ),
    )
    branch.process(validate_schema=False)
    return branch


def _named_branch(name: str, kind: str, car: NodeSchema, process: bool = False) -> SchemaBranch:
    branch = SchemaBranch(cache={}, name=name)
    branch.set(name=kind, schema=car)
    branch.set(name=PERSON_KIND, schema=NodeSchema(id="node-person", name="Person", namespace="Test"))
    if process:
        branch.process()
    return branch


def _regex(schema: SchemaBranch, attribute: str) -> str | None:
    parameters = schema.get(name=CAR_KIND).get_attribute(name=attribute).parameters
    assert isinstance(parameters, TextAttributeParameters)
    return parameters.regex


class TestWhichSideOwnsAProperty:
    """Every property the source did not change has to keep the destination's value."""

    @pytest.fixture(scope="class")
    def ancestor(self) -> SchemaBranch:
        return _branch("ancestor", _car_schema(code_regex=PERMISSIVE))

    def test_a_destination_change_survives_an_untouched_property(self, ancestor: SchemaBranch) -> None:
        source = _branch("source", _car_schema(code_regex=PERMISSIVE, color_regex=r"^#\w+$"))
        destination = _branch("destination", _car_schema(code_regex=UPPERCASE_ONLY))

        candidate = MergedSchemaBuilder().build(ancestor=ancestor, source=source, destination=destination)

        assert _regex(candidate, "code") == UPPERCASE_ONLY
        assert _regex(candidate, "color") == r"^#\w+$"

    def test_a_source_change_replaces_the_forked_value(self, ancestor: SchemaBranch) -> None:
        source = _branch("source", _car_schema(code_regex=LOWERCASE_ONLY))
        destination = _branch("destination", _car_schema(code_regex=PERMISSIVE))

        candidate = MergedSchemaBuilder().build(ancestor=ancestor, source=source, destination=destination)

        assert _regex(candidate, "code") == LOWERCASE_ONLY

    def test_the_source_wins_a_property_both_sides_changed(self, ancestor: SchemaBranch) -> None:
        source = _branch("source", _car_schema(code_regex=LOWERCASE_ONLY))
        destination = _branch("destination", _car_schema(code_regex=UPPERCASE_ONLY))

        candidate = MergedSchemaBuilder().build(ancestor=ancestor, source=source, destination=destination)

        assert _regex(candidate, "code") == LOWERCASE_ONLY

    def test_identical_branches_produce_the_destination_schema(self, ancestor: SchemaBranch) -> None:
        source = _branch("source", _car_schema(code_regex=PERMISSIVE))
        destination = _branch("destination", _car_schema(code_regex=PERMISSIVE))

        candidate = MergedSchemaBuilder().build(ancestor=ancestor, source=source, destination=destination)

        assert candidate.get_hash() == destination.get_hash()


class TestConflictsResolvedForTheDestination:
    """A property the user resolved in the destination's favour must not move."""

    @pytest.fixture(scope="class")
    def ancestor(self) -> SchemaBranch:
        return _branch("ancestor", _car_schema(code_regex=PERMISSIVE))

    def test_the_destination_value_is_kept(self, ancestor: SchemaBranch) -> None:
        source = _branch("source", _car_schema(code_regex=LOWERCASE_ONLY))
        destination = _branch("destination", _car_schema(code_regex=UPPERCASE_ONLY))

        candidate = MergedSchemaBuilder().build(
            ancestor=ancestor,
            source=source,
            destination=destination,
            keep_destination_property_map={CODE_ATTR_ID: {"parameters"}},
        )

        assert _regex(candidate, "code") == UPPERCASE_ONLY

    def test_other_properties_of_the_same_attribute_still_move(self, ancestor: SchemaBranch) -> None:
        source = _branch("source", _car_schema(code_regex=LOWERCASE_ONLY, code_optional=False))
        destination = _branch("destination", _car_schema(code_regex=UPPERCASE_ONLY, code_optional=True))

        candidate = MergedSchemaBuilder().build(
            ancestor=ancestor,
            source=source,
            destination=destination,
            keep_destination_property_map={CODE_ATTR_ID: {"parameters"}},
        )

        assert _regex(candidate, "code") == UPPERCASE_ONLY
        assert candidate.get(name=CAR_KIND).get_attribute(name="code").optional is False


class TestNodeLevelProperties:
    @pytest.fixture(scope="class")
    def ancestor(self) -> SchemaBranch:
        return _branch("ancestor", _car_schema())

    def test_a_source_change_moves(self, ancestor: SchemaBranch) -> None:
        source = _branch("source", _car_schema(uniqueness_constraints=[["code__value"]]))
        destination = _branch("destination", _car_schema())

        candidate = MergedSchemaBuilder().build(ancestor=ancestor, source=source, destination=destination)

        assert candidate.get(name=CAR_KIND).uniqueness_constraints == [["code__value"]]

    def test_a_destination_change_survives_an_unrelated_source_change(self, ancestor: SchemaBranch) -> None:
        source = _branch("source", _car_schema(code_regex=LOWERCASE_ONLY))
        destination = _branch("destination", _car_schema(uniqueness_constraints=[["code__value"]]))

        candidate = MergedSchemaBuilder().build(ancestor=ancestor, source=source, destination=destination)

        assert candidate.get(name=CAR_KIND).uniqueness_constraints == [["code__value"]]
        assert _regex(candidate, "code") == LOWERCASE_ONLY


class TestAttributesAddedAndRemoved:
    def test_an_attribute_the_source_added_lands_on_the_destination_node(self) -> None:
        ancestor = _branch("ancestor", _car_schema())
        source = _branch("source", _car_schema(extra_attribute="nickname"))
        destination = _branch("destination", _car_schema(code_regex=UPPERCASE_ONLY))

        candidate = MergedSchemaBuilder().build(ancestor=ancestor, source=source, destination=destination)

        car = candidate.get(name=CAR_KIND)
        assert sorted(attribute.name for attribute in car.attributes) == ["code", "color", "nickname"]
        assert _regex(candidate, "code") == UPPERCASE_ONLY

    def test_an_attribute_the_source_removed_leaves_the_destination_node(self) -> None:
        ancestor = _branch("ancestor", _car_schema(extra_attribute="nickname"))
        source = _branch("source", _car_schema())
        destination = _branch("destination", _car_schema(extra_attribute="nickname", code_regex=UPPERCASE_ONLY))

        candidate = MergedSchemaBuilder().build(ancestor=ancestor, source=source, destination=destination)

        car = candidate.get(name=CAR_KIND)
        assert sorted(attribute.name for attribute in car.attributes) == ["code", "color"]
        assert _regex(candidate, "code") == UPPERCASE_ONLY


class TestRenames:
    """Test building the SchemaBranch when elements are renamed."""

    def test_a_renamed_kind_lands_under_its_new_name(self) -> None:
        ancestor = _branch("ancestor", _car_schema())
        source = _renamed_kind_branch("source")
        destination = _branch("destination", _car_schema())

        candidate = MergedSchemaBuilder().build(ancestor=ancestor, source=source, destination=destination)

        assert candidate.has(name="TestVehicle")
        assert not candidate.has(name=CAR_KIND)

    def test_a_renamed_kind_keeps_its_attributes_and_relationships(self) -> None:
        ancestor = _branch("ancestor", _car_schema())
        source = _renamed_kind_branch("source")
        destination = _branch("destination", _car_schema())

        candidate = MergedSchemaBuilder().build(ancestor=ancestor, source=source, destination=destination)

        vehicle = candidate.get(name="TestVehicle")
        assert sorted(attribute.name for attribute in vehicle.attributes) == ["code", "color"]
        assert sorted(relationship.name for relationship in vehicle.relationships) == ["owner"]

    def test_a_renamed_kind_takes_the_generated_profile_with_it(self) -> None:
        """Deleting the old kind takes its generated schemas, and nothing regenerates them here."""
        ancestor = _branch("ancestor", _car_schema(), process=True)
        source = _renamed_kind_branch("source", process=True)
        destination = _branch("destination", _car_schema(), process=True)

        candidate = MergedSchemaBuilder().build(ancestor=ancestor, source=source, destination=destination)

        assert "ProfileTestVehicle" in candidate.profile_names
        assert "ProfileTestCar" not in candidate.profile_names

    def test_a_renamed_kind_keeps_an_untouched_destination_property(self) -> None:
        ancestor = _branch("ancestor", _car_schema())
        renamed = _car_schema()
        renamed.name = "Vehicle"
        source = SchemaBranch(cache={}, name="source")
        source.set(name="TestVehicle", schema=renamed)
        destination = _branch("destination", _car_schema(uniqueness_constraints=[["code__value"]]))

        candidate = MergedSchemaBuilder().build(ancestor=ancestor, source=source, destination=destination)

        assert candidate.get(name="TestVehicle").uniqueness_constraints == [["code__value"]]

    def test_a_renamed_attribute_lands_under_its_new_name(self) -> None:
        ancestor = _branch("ancestor", _car_schema())
        renamed = _car_schema()
        renamed.get_attribute(name="code").name = "reference"
        source = _branch("source", renamed)
        destination = _branch("destination", _car_schema())

        candidate = MergedSchemaBuilder().build(ancestor=ancestor, source=source, destination=destination)

        car = candidate.get(name=CAR_KIND)
        assert sorted(attribute.name for attribute in car.attributes) == ["color", "reference"]

    def test_a_renamed_relationship_lands_under_its_new_name(self) -> None:
        """A relationship rename needs no migration, but the merged schema still has to carry it."""
        ancestor = _branch("ancestor", _car_schema())
        renamed = _car_schema()
        renamed.get_relationship(name="owner").name = "driver"
        source = _branch("source", renamed)
        destination = _branch("destination", _car_schema())

        candidate = MergedSchemaBuilder().build(ancestor=ancestor, source=source, destination=destination)

        car = candidate.get(name=CAR_KIND)
        assert sorted(relationship.name for relationship in car.relationships) == ["driver"]

    def test_a_renamed_relationship_keeps_an_untouched_destination_property(self) -> None:
        ancestor = _branch("ancestor", _car_schema())
        renamed = _car_schema()
        renamed.get_relationship(name="owner").name = "driver"
        source = _branch("source", renamed)
        narrowed = _car_schema()
        narrowed.get_relationship(name="owner").optional = False
        destination = _branch("destination", narrowed)

        candidate = MergedSchemaBuilder().build(ancestor=ancestor, source=source, destination=destination)

        assert candidate.get(name=CAR_KIND).get_relationship(name="driver").optional is False

    def test_a_renamed_inherited_attribute_lands_under_its_new_name(self) -> None:
        """An inherited element carries no id of its own, so the diff keys it on the id it came from."""
        ancestor = _inheriting_branch("ancestor", inherited_name="code")
        source = _inheriting_branch("source", inherited_name="reference")
        destination = _inheriting_branch("destination", inherited_name="code")

        candidate = MergedSchemaBuilder().build(ancestor=ancestor, source=source, destination=destination)

        car = candidate.get(name=CAR_KIND)
        assert sorted(attribute.name for attribute in car.attributes) == ["color", "reference"]

    def test_a_renamed_attribute_keeps_an_untouched_destination_property(self) -> None:
        ancestor = _branch("ancestor", _car_schema(code_regex=PERMISSIVE))
        renamed = _car_schema(code_regex=PERMISSIVE)
        renamed.get_attribute(name="code").name = "reference"
        source = _branch("source", renamed)
        destination = _branch("destination", _car_schema(code_regex=UPPERCASE_ONLY))

        candidate = MergedSchemaBuilder().build(ancestor=ancestor, source=source, destination=destination)

        parameters = candidate.get(name=CAR_KIND).get_attribute(name="reference").parameters
        assert isinstance(parameters, TextAttributeParameters)
        assert parameters.regex == UPPERCASE_ONLY


class TestKindsAddedAndRemoved:
    def test_a_kind_the_source_added_lands_on_the_candidate(self) -> None:
        ancestor = _branch("ancestor", _car_schema())
        source = _branch("source", _car_schema())
        source.set(name=TRUCK_KIND, schema=NodeSchema(name="Truck", namespace="Test"))
        destination = _branch("destination", _car_schema())

        candidate = MergedSchemaBuilder().build(ancestor=ancestor, source=source, destination=destination)

        assert candidate.has(name=TRUCK_KIND)

    def test_a_kind_the_source_removed_leaves_the_candidate(self) -> None:
        ancestor = _branch("ancestor", _car_schema())
        ancestor.set(name=TRUCK_KIND, schema=NodeSchema(name="Truck", namespace="Test"))
        source = _branch("source", _car_schema())
        destination = _branch("destination", _car_schema())
        destination.set(name=TRUCK_KIND, schema=NodeSchema(name="Truck", namespace="Test"))

        candidate = MergedSchemaBuilder().build(ancestor=ancestor, source=source, destination=destination)

        assert not candidate.has(name=TRUCK_KIND)
