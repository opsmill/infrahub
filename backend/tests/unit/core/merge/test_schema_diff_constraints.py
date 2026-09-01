"""Constraints contributed by comparing the two branch schemas against their common ancestor.

A schema property change has to be checked against the whole population, whatever else the branch
carries, so every constraint produced here must arrive unrestricted (``node_uuids is None``). Which
side of the fork made the change makes no difference.
"""

from __future__ import annotations

import pytest

from infrahub.core.constants import SchemaPathType
from infrahub.core.merge.schema_analyzer import MergeSchemaAnalyzer
from infrahub.core.models import SchemaUpdateConstraintInfo, SchemaUpdateValidationResult
from infrahub.core.path import SchemaPath
from infrahub.core.schema import AttributeSchema, NodeSchema
from infrahub.core.schema.attribute_parameters import TextAttributeParameters
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.core.validators import CONSTRAINT_VALIDATOR_MAP
from infrahub.core.validators.enum import ConstraintIdentifier

CAR_KIND = "TestCar"
CAR_NODE_ID = "node-car"
COLOR_ATTR_ID = "attr-color"


def _car(
    color_regex: str | None = None,
    color_enum: list[str] | None = None,
    color_kind: str = "Text",
) -> NodeSchema:
    return NodeSchema(
        id=CAR_NODE_ID,
        name="Car",
        namespace="Test",
        attributes=[
            AttributeSchema(
                id=COLOR_ATTR_ID,
                name="color",
                kind=color_kind,
                optional=True,
                enum=color_enum,
                parameters=TextAttributeParameters(regex=color_regex),
            )
        ],
    )


def _branch(name: str, car: NodeSchema) -> SchemaBranch:
    branch = SchemaBranch(cache={}, name=name)
    branch.set(name=CAR_KIND, schema=car)
    return branch


def _expected(property_name: str, constraint_name: str) -> SchemaUpdateConstraintInfo:
    return SchemaUpdateConstraintInfo(
        constraint_name=constraint_name,
        path=SchemaPath(
            path_type=SchemaPathType.ATTRIBUTE,
            schema_kind=CAR_KIND,
            field_name="color",
            property_name=property_name,
        ),
    )


class TestWhichSideChangedTheProperty:
    """The comparison sums both sides of the fork, so the same constraint arrives either way."""

    REGEX = r"^[A-Z][a-z]+$"

    @pytest.fixture(scope="class")
    def ancestor(self) -> SchemaBranch:
        return _branch("ancestor", _car())

    @pytest.fixture(scope="class")
    def expected(self) -> SchemaUpdateConstraintInfo:
        return _expected(
            property_name="parameters.regex",
            constraint_name=ConstraintIdentifier.ATTRIBUTE_PARAMETERS_REGEX_UPDATE.value,
        )

    def test_a_change_on_the_source(self, ancestor: SchemaBranch, expected: SchemaUpdateConstraintInfo) -> None:
        source = _branch("source", _car(color_regex=self.REGEX))
        destination = _branch("destination", _car())

        constraints = MergeSchemaAnalyzer.schema_diff_constraints(
            ancestor=ancestor, source=source, destination=destination, target_schema=source
        )

        assert set(constraints) == {expected}
        assert {constraint.node_uuids for constraint in constraints} == {None}

    def test_a_change_on_the_destination(self, ancestor: SchemaBranch, expected: SchemaUpdateConstraintInfo) -> None:
        source = _branch("source", _car())
        destination = _branch("destination", _car(color_regex=self.REGEX))

        constraints = MergeSchemaAnalyzer.schema_diff_constraints(
            ancestor=ancestor, source=source, destination=destination, target_schema=destination
        )

        assert set(constraints) == {expected}
        assert {constraint.node_uuids for constraint in constraints} == {None}


class TestConstraintFamilies:
    @pytest.fixture(scope="class")
    def ancestor(self) -> SchemaBranch:
        return _branch("ancestor", _car())

    def test_an_enum_change(self, ancestor: SchemaBranch) -> None:
        source = _branch("source", _car(color_enum=["red", "blue"]))
        destination = _branch("destination", _car())

        constraints = MergeSchemaAnalyzer.schema_diff_constraints(
            ancestor=ancestor, source=source, destination=destination, target_schema=source
        )

        assert set(constraints) == {_expected(property_name="enum", constraint_name="attribute.enum.update")}
        assert {constraint.node_uuids for constraint in constraints} == {None}

    def test_a_property_gated_on_a_migration(self, ancestor: SchemaBranch) -> None:
        """A migration-gated change produces a migration entry, not a constraint, so it is converted back.

        Without the conversion the check would only ever arrive node-scoped from the data diff, and a
        branch carrying no data change for the kind would never be checked at all.
        """
        source = _branch("source", _car(color_kind="TextArea"))
        destination = _branch("destination", _car())

        constraints = MergeSchemaAnalyzer.schema_diff_constraints(
            ancestor=ancestor, source=source, destination=destination, target_schema=source
        )

        assert set(constraints) == {_expected(property_name="kind", constraint_name="attribute.kind.update")}
        assert {constraint.node_uuids for constraint in constraints} == {None}

    def test_the_migration_survives_the_conversion(self, ancestor: SchemaBranch) -> None:
        """The conversion adds a constraint; it must not consume the migration entry.

        Validators run before the merge writes and migrations after it, so a property needing both
        gets both. Losing the migration would leave the data in its pre-merge shape with nothing left
        to correct it.
        """
        source = _branch("source", _car(color_kind="TextArea"))
        destination = _branch("destination", _car())

        diff = MergeSchemaAnalyzer.three_way_schema_diff(ancestor=ancestor, source=source, destination=destination)
        validation = SchemaUpdateValidationResult.init(diff=diff, schema=source)
        validation.add_validator_for_migration(validator_map=CONSTRAINT_VALIDATOR_MAP)

        assert [migration.migration_name for migration in validation.migrations] == ["attribute.kind.update"]
        assert [constraint.constraint_name for constraint in validation.constraints] == ["attribute.kind.update"]


class TestNothingChanged:
    def test_identical_schemas_produce_no_constraints(self) -> None:
        ancestor = _branch("ancestor", _car(color_regex=r".*"))
        source = _branch("source", _car(color_regex=r".*"))
        destination = _branch("destination", _car(color_regex=r".*"))

        constraints = MergeSchemaAnalyzer.schema_diff_constraints(
            ancestor=ancestor, source=source, destination=destination, target_schema=destination
        )

        assert constraints == []
