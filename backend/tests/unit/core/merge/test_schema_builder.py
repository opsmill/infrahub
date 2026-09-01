"""The schema a merge or rebase produces, built from the source branch's own changes only."""

from __future__ import annotations

import pytest

from infrahub.core.merge.schema_builder import MergedSchemaBuilder
from infrahub.core.schema import AttributeSchema, NodeSchema
from infrahub.core.schema.attribute_parameters import TextAttributeParameters
from infrahub.core.schema.schema_branch import SchemaBranch

CAR_KIND = "TestCar"
TRUCK_KIND = "TestTruck"
CODE_ATTR_ID = "attr-code"
COLOR_ATTR_ID = "attr-color"
CAR_NODE_ID = "node-car"

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
        uniqueness_constraints=uniqueness_constraints,
    )


def _branch(name: str, car: NodeSchema) -> SchemaBranch:
    branch = SchemaBranch(cache={}, name=name)
    branch.set(name=CAR_KIND, schema=car)
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
