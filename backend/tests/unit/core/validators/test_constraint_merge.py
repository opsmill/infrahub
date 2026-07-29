from infrahub.core.constants import SchemaPathType
from infrahub.core.models import SchemaUpdateConstraintInfo
from infrahub.core.path import SchemaPath
from infrahub.core.schema.generic_schema import GenericSchema
from infrahub.core.schema.node_schema import NodeSchema
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.core.validators.constraint_merge import build_constraint_info_merger
from infrahub.core.validators.enum import ConstraintIdentifier

UNIQUENESS = ConstraintIdentifier.NODE_UNIQUENESS_CONSTRAINTS_UPDATE.value


def _uniqueness_info(kind: str, node_uuids: list[str] | None) -> SchemaUpdateConstraintInfo:
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


def _schema_branch() -> SchemaBranch:
    branch = SchemaBranch(cache={}, name="test")
    branch.set(
        name="TestCar", schema=GenericSchema(name="Car", namespace="Test", uniqueness_constraints=[["name__value"]])
    )
    branch.set(
        name="TestElectricCar",
        schema=NodeSchema(
            name="ElectricCar", namespace="Test", inherit_from=["TestCar"], uniqueness_constraints=[["name__value"]]
        ),
    )
    branch.set(
        name="TestPerson",
        schema=NodeSchema(name="Person", namespace="Test", uniqueness_constraints=[["name__value"]]),
    )
    return branch


class TestConstraintInfoMergerPrecedence:
    """The cross-producer collapse that runs before generic/node deduplication."""

    def test_full_scan_wins_over_node_scoped(self) -> None:
        # a constraint both broadened (schema diff, full scan) and data-changed collapses to a full scan
        merger = build_constraint_info_merger(schema_branch=_schema_branch())
        data_diff = [_uniqueness_info("TestCar", node_uuids=["a", "b"])]
        schema_diff = [_uniqueness_info("TestCar", node_uuids=None)]

        result = merger.merge(data_diff, schema_diff)

        assert result == [_uniqueness_info("TestCar", node_uuids=None)]

    def test_full_scan_wins_regardless_of_order(self) -> None:
        merger = build_constraint_info_merger(schema_branch=_schema_branch())
        schema_diff = [_uniqueness_info("TestCar", node_uuids=None)]
        data_diff = [_uniqueness_info("TestCar", node_uuids=["a", "b"])]

        result = merger.merge(schema_diff, data_diff)

        assert result == [_uniqueness_info("TestCar", node_uuids=None)]

    def test_two_node_scoped_entries_union_their_nodes(self) -> None:
        merger = build_constraint_info_merger(schema_branch=_schema_branch())

        result = merger.merge(
            [_uniqueness_info("TestCar", node_uuids=["a", "b"])],
            [_uniqueness_info("TestCar", node_uuids=["b", "c"])],
        )

        assert result == [_uniqueness_info("TestCar", node_uuids=["a", "b", "c"])]

    def test_distinct_constraints_are_preserved(self) -> None:
        merger = build_constraint_info_merger(schema_branch=_schema_branch())

        result = merger.merge(
            [_uniqueness_info("TestCar", node_uuids=["a"])],
            [_uniqueness_info("TestPerson", node_uuids=["b"])],
        )

        assert {c.path.schema_kind: c.node_uuids for c in result} == {"TestCar": ["a"], "TestPerson": ["b"]}


class TestConstraintInfoMerger:
    def test_merges_then_deduplicates(self) -> None:
        # the data diff scopes the generic; the schema diff broadens it to the full population; and
        # the inherited node check must be dropped as covered by the generic
        merger = build_constraint_info_merger(schema_branch=_schema_branch())
        data_diff = [
            _uniqueness_info("TestCar", node_uuids=["e1"]),
            _uniqueness_info("TestElectricCar", node_uuids=["e1"]),
        ]
        schema_diff = [_uniqueness_info("TestCar", node_uuids=None)]

        result = merger.merge(data_diff, schema_diff)

        # merge precedence keeps the full-population generic; dedup then removes the covered node
        assert result == [_uniqueness_info("TestCar", node_uuids=None)]
