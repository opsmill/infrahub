"""Constraints contributed by comparing the two branch schemas with the schema the operation produces.

A schema property change has to be checked against the whole population, whatever else the branch
carries, so every constraint produced here must arrive unrestricted (``node_uuids is None``). Which
side of the fork made the change makes no difference, and a renamed element is reported under the
name the target schema knows it by.
"""

from __future__ import annotations

import pytest

from infrahub.core.constants import SchemaPathType
from infrahub.core.merge.schema_analyzer import MergeSchemaAnalyzer
from infrahub.core.merge.schema_builder import MergedSchemaBuilder
from infrahub.core.models import SchemaUpdateConstraintInfo, SchemaUpdateValidationResult
from infrahub.core.path import SchemaPath
from infrahub.core.schema import AttributeSchema, NodeSchema, RelationshipSchema
from infrahub.core.schema.attribute_parameters import TextAttributeParameters
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.core.validators import CONSTRAINT_VALIDATOR_MAP
from infrahub.core.validators.enum import ConstraintIdentifier

CAR_KIND = "TestCar"
CAR_NODE_ID = "node-car"
COLOR_ATTR_ID = "attr-color"
OWNER_REL_ID = "rel-owner"
REGEX = r"^[A-Z][a-z]+$"


def _car(
    color_regex: str | None = None,
    color_enum: list[str] | None = None,
    color_kind: str = "Text",
    owner_optional: bool = True,
    **names: str,
) -> NodeSchema:
    """A car kind whose elements all carry ids, so a rename is a rename and not a remove plus an add.

    ``names`` renames an element: ``car="Auto"``, ``color="colour"``, ``owner="driver"``.
    """
    return NodeSchema(
        id=CAR_NODE_ID,
        name=names.get("car", "Car"),
        namespace="Test",
        attributes=[
            AttributeSchema(
                id=COLOR_ATTR_ID,
                name=names.get("color", "color"),
                kind=color_kind,
                optional=True,
                enum=color_enum,
                parameters=TextAttributeParameters(regex=color_regex),
            )
        ],
        relationships=[
            RelationshipSchema(
                id=OWNER_REL_ID,
                name=names.get("owner", "owner"),
                peer="TestPerson",
                cardinality="one",
                optional=owner_optional,
            )
        ],
    )


def _branch(name: str, car: NodeSchema) -> SchemaBranch:
    branch = SchemaBranch(cache={}, name=name)
    branch.set(name=car.kind, schema=car)
    return branch


def _expected(
    property_name: str,
    constraint_name: str,
    schema_kind: str = CAR_KIND,
    field_name: str = "color",
    path_type: SchemaPathType = SchemaPathType.ATTRIBUTE,
) -> SchemaUpdateConstraintInfo:
    return SchemaUpdateConstraintInfo(
        constraint_name=constraint_name,
        path=SchemaPath(
            path_type=path_type,
            schema_kind=schema_kind,
            field_name=field_name,
            property_name=property_name,
        ),
    )


def _merged(ancestor: SchemaBranch, source: SchemaBranch, destination: SchemaBranch) -> SchemaBranch:
    """The schema the merge produces, built the way production builds it."""
    return MergedSchemaBuilder().build(ancestor=ancestor, source=source, destination=destination)


class TestWhichSideChangedTheProperty:
    """The comparison sums both sides of the fork, so the same constraint arrives either way."""

    REGEX = REGEX

    @pytest.fixture(scope="class")
    def expected(self) -> SchemaUpdateConstraintInfo:
        return _expected(
            property_name="parameters.regex",
            constraint_name=ConstraintIdentifier.ATTRIBUTE_PARAMETERS_REGEX_UPDATE.value,
        )

    def test_a_change_on_the_source(self, expected: SchemaUpdateConstraintInfo) -> None:
        source = _branch("source", _car(color_regex=self.REGEX))
        destination = _branch("destination", _car())

        constraints = MergeSchemaAnalyzer.schema_diff_constraints(
            source=source, destination=destination, target_schema=source
        )

        assert set(constraints) == {expected}
        assert {constraint.node_uuids for constraint in constraints} == {None}

    def test_a_change_on_the_destination(self, expected: SchemaUpdateConstraintInfo) -> None:
        source = _branch("source", _car())
        destination = _branch("destination", _car(color_regex=self.REGEX))

        constraints = MergeSchemaAnalyzer.schema_diff_constraints(
            source=source, destination=destination, target_schema=destination
        )

        assert set(constraints) == {expected}
        assert {constraint.node_uuids for constraint in constraints} == {None}


class TestConstraintFamilies:
    def test_an_enum_change(self) -> None:
        source = _branch("source", _car(color_enum=["red", "blue"]))
        destination = _branch("destination", _car())

        constraints = MergeSchemaAnalyzer.schema_diff_constraints(
            source=source, destination=destination, target_schema=source
        )

        assert set(constraints) == {_expected(property_name="enum", constraint_name="attribute.enum.update")}
        assert {constraint.node_uuids for constraint in constraints} == {None}

    def test_a_property_gated_on_a_migration(self) -> None:
        """A migration-gated change produces a migration entry, not a constraint, so it is converted back.

        Without the conversion the check would only ever arrive node-scoped from the data diff, and a
        branch carrying no data change for the kind would never be checked at all.
        """
        source = _branch("source", _car(color_kind="TextArea"))
        destination = _branch("destination", _car())

        constraints = MergeSchemaAnalyzer.schema_diff_constraints(
            source=source, destination=destination, target_schema=source
        )

        assert set(constraints) == {_expected(property_name="kind", constraint_name="attribute.kind.update")}
        assert {constraint.node_uuids for constraint in constraints} == {None}

    def test_the_migration_survives_the_conversion(self) -> None:
        """The conversion adds a constraint; it must not consume the migration entry.

        Validators run before the merge writes and migrations after it, so a property needing both
        gets both. Losing the migration would leave the data in its pre-merge shape with nothing left
        to correct it.
        """
        source = _branch("source", _car(color_kind="TextArea"))
        destination = _branch("destination", _car())

        diff = MergeSchemaAnalyzer.three_way_schema_diff(source=source, destination=destination, target=source)
        validation = SchemaUpdateValidationResult.init(diff=diff, schema=source)
        validation.add_validator_for_migration(validator_map=CONSTRAINT_VALIDATOR_MAP)

        assert [migration.migration_name for migration in validation.migrations] == ["attribute.kind.update"]
        assert [constraint.constraint_name for constraint in validation.constraints] == ["attribute.kind.update"]


class TestNothingChanged:
    def test_identical_schemas_produce_no_constraints(self) -> None:
        source = _branch("source", _car(color_regex=r".*"))
        destination = _branch("destination", _car(color_regex=r".*"))

        constraints = MergeSchemaAnalyzer.schema_diff_constraints(
            source=source, destination=destination, target_schema=destination
        )

        assert constraints == []


class TestRenamedElements:
    """A rename on one side and a change on the other must meet under the target's name.

    Each side's diff is keyed by the names of the schema it is compared with. Keyed by the ancestor,
    the two halves disagree about what a renamed element is called and the half carrying the old name
    cannot be resolved against the merged schema at all; keyed by the target, both halves speak of
    the element the validation will actually look up.
    """

    @pytest.fixture(scope="class")
    def ancestor(self) -> SchemaBranch:
        return _branch("ancestor", _car())

    def test_a_source_rename_with_a_destination_change_on_the_same_attribute(self, ancestor: SchemaBranch) -> None:
        source = _branch("source", _car(color="colour"))
        destination = _branch("destination", _car(color_regex=REGEX))
        target = _merged(ancestor=ancestor, source=source, destination=destination)

        constraints = MergeSchemaAnalyzer.schema_diff_constraints(
            source=source, destination=destination, target_schema=target
        )

        assert set(constraints) == {
            _expected(
                property_name="parameters.regex",
                constraint_name=ConstraintIdentifier.ATTRIBUTE_PARAMETERS_REGEX_UPDATE.value,
                field_name="colour",
            )
        }

    def test_a_destination_rename_with_a_source_change_on_the_same_attribute(self, ancestor: SchemaBranch) -> None:
        source = _branch("source", _car(color_regex=REGEX))
        destination = _branch("destination", _car(color="colour"))
        target = _merged(ancestor=ancestor, source=source, destination=destination)

        constraints = MergeSchemaAnalyzer.schema_diff_constraints(
            source=source, destination=destination, target_schema=target
        )

        assert set(constraints) == {
            _expected(
                property_name="parameters.regex",
                constraint_name=ConstraintIdentifier.ATTRIBUTE_PARAMETERS_REGEX_UPDATE.value,
                field_name="colour",
            )
        }

    def test_a_source_kind_rename_with_a_destination_change_on_the_kind(self, ancestor: SchemaBranch) -> None:
        source = _branch("source", _car(car="Auto"))
        destination = _branch("destination", _car(color_regex=REGEX))
        target = _merged(ancestor=ancestor, source=source, destination=destination)

        constraints = MergeSchemaAnalyzer.schema_diff_constraints(
            source=source, destination=destination, target_schema=target
        )

        assert set(constraints) == {
            _expected(
                property_name="parameters.regex",
                constraint_name=ConstraintIdentifier.ATTRIBUTE_PARAMETERS_REGEX_UPDATE.value,
                schema_kind="TestAuto",
            )
        }

    def test_a_destination_kind_rename_with_a_source_change_on_the_kind(self, ancestor: SchemaBranch) -> None:
        source = _branch("source", _car(color_regex=REGEX))
        destination = _branch("destination", _car(car="Auto"))
        target = _merged(ancestor=ancestor, source=source, destination=destination)

        constraints = MergeSchemaAnalyzer.schema_diff_constraints(
            source=source, destination=destination, target_schema=target
        )

        assert set(constraints) == {
            _expected(
                property_name="parameters.regex",
                constraint_name=ConstraintIdentifier.ATTRIBUTE_PARAMETERS_REGEX_UPDATE.value,
                schema_kind="TestAuto",
            )
        }

    def test_a_source_relationship_rename_with_a_destination_change_on_it(self, ancestor: SchemaBranch) -> None:
        source = _branch("source", _car(owner="driver"))
        destination = _branch("destination", _car(owner_optional=False))
        target = _merged(ancestor=ancestor, source=source, destination=destination)

        constraints = MergeSchemaAnalyzer.schema_diff_constraints(
            source=source, destination=destination, target_schema=target
        )

        assert set(constraints) == {
            _expected(
                property_name="optional",
                constraint_name="relationship.optional.update",
                field_name="driver",
                path_type=SchemaPathType.RELATIONSHIP,
            )
        }

    def test_the_migration_for_a_renamed_kind_targets_the_new_name(self, ancestor: SchemaBranch) -> None:
        """Migrations resolve the kind on the target too, so they must carry the new name as well."""
        source = _branch("source", _car(car="Auto"))
        destination = _branch("destination", _car(color_kind="TextArea"))
        target = _merged(ancestor=ancestor, source=source, destination=destination)

        diff = MergeSchemaAnalyzer.three_way_schema_diff(source=source, destination=destination, target=target)
        validation = SchemaUpdateValidationResult.init(diff=diff, schema=target)

        assert {(m.migration_name, m.path.schema_kind) for m in validation.migrations} == {
            ("node.name.update", "TestAuto"),
            ("attribute.kind.update", "TestAuto"),
        }
