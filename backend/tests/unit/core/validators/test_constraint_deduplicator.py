from infrahub.core.constants import SchemaPathType
from infrahub.core.models import SchemaUpdateConstraintInfo
from infrahub.core.path import SchemaPath
from infrahub.core.schema.generic_schema import GenericSchema
from infrahub.core.schema.node_schema import NodeSchema
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.core.validators.enum import ConstraintIdentifier
from infrahub.core.validators.uniqueness.deduplicator import UniquenessConstraintDeduplicator

UNIQUENESS = ConstraintIdentifier.NODE_UNIQUENESS_CONSTRAINTS_UPDATE.value


def _uniqueness_info(kind: str, node_uuids: list[str] | None = None) -> SchemaUpdateConstraintInfo:
    return SchemaUpdateConstraintInfo(
        constraint_name=UNIQUENESS,
        path=SchemaPath(
            path_type=SchemaPathType.NODE,
            schema_kind=kind,
            field_name="uniqueness_constraints",
            property_name="uniqueness_constraints",
        ),
        node_uuids=node_uuids,
    )


def _attribute_info(kind: str) -> SchemaUpdateConstraintInfo:
    return SchemaUpdateConstraintInfo(
        constraint_name="attribute.unique.update",
        path=SchemaPath(
            path_type=SchemaPathType.ATTRIBUTE, schema_kind=kind, field_name="name", property_name="unique"
        ),
    )


def _schema_branch() -> SchemaBranch:
    """A generic ``TestCar`` and implementations, plus an unrelated standalone ``TestPerson``.

    ElectricCar/GazCar inherit the generic's single constraint group; SpecialCar adds one of its
    own; Person shares no inheritance.
    """
    branch = SchemaBranch(cache={}, name="test")
    branch.set(
        name="TestCar",
        schema=GenericSchema(name="Car", namespace="Test", uniqueness_constraints=[["name__value"]]),
    )
    branch.set(
        name="TestElectricCar",
        schema=NodeSchema(name="ElectricCar", namespace="Test", inherit_from=["TestCar"], uniqueness_constraints=[["name__value"]]),
    )
    branch.set(
        name="TestGazCar",
        schema=NodeSchema(name="GazCar", namespace="Test", inherit_from=["TestCar"], uniqueness_constraints=[["name__value"]]),
    )
    branch.set(
        name="TestSpecialCar",
        schema=NodeSchema(
            name="SpecialCar",
            namespace="Test",
            inherit_from=["TestCar"],
            uniqueness_constraints=[["name__value"], ["special__value"]],
        ),
    )
    branch.set(
        name="TestPerson",
        schema=NodeSchema(name="Person", namespace="Test", uniqueness_constraints=[["name__value"]]),
    )
    return branch


def _remaining_uniqueness_kinds(constraints: list[SchemaUpdateConstraintInfo]) -> set[str]:
    return {c.path.schema_kind for c in constraints if c.constraint_name == UNIQUENESS}


class TestUniquenessConstraintDeduplicator:
    def test_inherited_node_dropped_when_generic_covers_it_full_population(self) -> None:
        deduplicator = UniquenessConstraintDeduplicator(schema_branch=_schema_branch())
        constraints = [_uniqueness_info("TestCar"), _uniqueness_info("TestElectricCar")]

        result = deduplicator.deduplicate(constraints)

        assert _remaining_uniqueness_kinds(result) == {"TestCar"}

    def test_all_implementers_dropped_when_generic_covers_them(self) -> None:
        # the generic's scope is the union of the implementers' changed nodes
        deduplicator = UniquenessConstraintDeduplicator(schema_branch=_schema_branch())
        constraints = [
            _uniqueness_info("TestCar", node_uuids=["e1", "g1"]),
            _uniqueness_info("TestElectricCar", node_uuids=["e1"]),
            _uniqueness_info("TestGazCar", node_uuids=["g1"]),
        ]

        result = deduplicator.deduplicate(constraints)

        assert _remaining_uniqueness_kinds(result) == {"TestCar"}

    def test_node_with_own_group_is_kept(self) -> None:
        # SpecialCar has a `special` group the generic does not cover, so it cannot be dropped
        deduplicator = UniquenessConstraintDeduplicator(schema_branch=_schema_branch())
        constraints = [_uniqueness_info("TestCar"), _uniqueness_info("TestSpecialCar")]

        result = deduplicator.deduplicate(constraints)

        assert _remaining_uniqueness_kinds(result) == {"TestCar", "TestSpecialCar"}

    def test_full_population_node_not_dropped_for_scoped_generic(self) -> None:
        # dropping a full-population node for a scoped generic would silently narrow the check
        deduplicator = UniquenessConstraintDeduplicator(schema_branch=_schema_branch())
        constraints = [
            _uniqueness_info("TestCar", node_uuids=["e1"]),
            _uniqueness_info("TestElectricCar", node_uuids=None),
        ]

        result = deduplicator.deduplicate(constraints)

        assert _remaining_uniqueness_kinds(result) == {"TestCar", "TestElectricCar"}

    def test_node_not_dropped_when_generic_scope_does_not_cover_it(self) -> None:
        deduplicator = UniquenessConstraintDeduplicator(schema_branch=_schema_branch())
        constraints = [
            _uniqueness_info("TestCar", node_uuids=["other"]),
            _uniqueness_info("TestElectricCar", node_uuids=["e1"]),
        ]

        result = deduplicator.deduplicate(constraints)

        assert _remaining_uniqueness_kinds(result) == {"TestCar", "TestElectricCar"}

    def test_scoped_node_dropped_when_generic_scope_is_superset(self) -> None:
        deduplicator = UniquenessConstraintDeduplicator(schema_branch=_schema_branch())
        constraints = [
            _uniqueness_info("TestCar", node_uuids=["e1", "e2", "g1"]),
            _uniqueness_info("TestElectricCar", node_uuids=["e1", "e2"]),
        ]

        result = deduplicator.deduplicate(constraints)

        assert _remaining_uniqueness_kinds(result) == {"TestCar"}

    def test_node_kept_when_generic_absent_from_set(self) -> None:
        deduplicator = UniquenessConstraintDeduplicator(schema_branch=_schema_branch())
        constraints = [_uniqueness_info("TestElectricCar")]

        result = deduplicator.deduplicate(constraints)

        assert _remaining_uniqueness_kinds(result) == {"TestElectricCar"}

    def test_standalone_node_is_kept(self) -> None:
        deduplicator = UniquenessConstraintDeduplicator(schema_branch=_schema_branch())
        constraints = [_uniqueness_info("TestCar"), _uniqueness_info("TestPerson")]

        result = deduplicator.deduplicate(constraints)

        assert _remaining_uniqueness_kinds(result) == {"TestCar", "TestPerson"}

    def test_non_uniqueness_constraints_pass_through(self) -> None:
        deduplicator = UniquenessConstraintDeduplicator(schema_branch=_schema_branch())
        attribute = _attribute_info("TestElectricCar")
        constraints = [_uniqueness_info("TestCar"), _uniqueness_info("TestElectricCar"), attribute]

        result = deduplicator.deduplicate(constraints)

        assert _remaining_uniqueness_kinds(result) == {"TestCar"}
        assert attribute in result
