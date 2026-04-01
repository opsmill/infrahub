import pytest

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import BranchSupportType, PathType, SchemaPathType
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.path import DataPath, SchemaPath
from infrahub.core.schema import NodeSchema, SchemaRoot
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.core.validators.attribute.kind import AttributeKindChecker, AttributeKindUpdateValidatorQuery
from infrahub.core.validators.model import SchemaConstraintValidatorRequest
from infrahub.database import InfrahubDatabase
from infrahub.exceptions import ValidationError


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _build_float_schema_root() -> SchemaRoot:
    """Schema with a Float attribute for testing."""
    node_schema = {
        "name": "Measurement",
        "namespace": "Test",
        "default_filter": "label__value",
        "display_labels": ["label__value"],
        "branch": BranchSupportType.AWARE.value,
        "attributes": [
            {"name": "label", "kind": "Text", "unique": True},
            {"name": "weight", "kind": "Float"},
            {"name": "height", "kind": "Float", "optional": True},
        ],
    }
    return SchemaRoot(nodes=[NodeSchema(**node_schema)])


def _build_constrained_float_schema_root() -> SchemaRoot:
    """Schema with constrained Float attributes (min/max)."""
    node_schema = {
        "name": "Sensor",
        "namespace": "Test",
        "default_filter": "label__value",
        "display_labels": ["label__value"],
        "branch": BranchSupportType.AWARE.value,
        "attributes": [
            {"name": "label", "kind": "Text", "unique": True},
            {
                "name": "temperature",
                "kind": "Float",
                "parameters": {"min_value": -40.0, "max_value": 85.0},
            },
        ],
    }
    return SchemaRoot(nodes=[NodeSchema(**node_schema)])


def _build_default_float_schema_root() -> SchemaRoot:
    """Schema with Float attribute that has a default_value."""
    node_schema = {
        "name": "Device",
        "namespace": "Test",
        "default_filter": "label__value",
        "display_labels": ["label__value"],
        "branch": BranchSupportType.AWARE.value,
        "attributes": [
            {"name": "label", "kind": "Text", "unique": True},
            {"name": "rack_units", "kind": "Float", "default_value": 1.5},
        ],
    }
    return SchemaRoot(nodes=[NodeSchema(**node_schema)])


def _register_schema(branch: Branch, schema_root: SchemaRoot) -> SchemaBranch:
    registry.schema.register_schema(schema=schema_root, branch=branch.name)
    registry.schema.process_schema_branch(name=branch.name)
    return registry.schema.get_schema_branch(name=branch.name)


@pytest.fixture
async def float_schema(
    db: InfrahubDatabase,
    default_branch: Branch,
    group_schema: None,
    data_schema: None,
) -> SchemaBranch:
    return _register_schema(branch=default_branch, schema_root=_build_float_schema_root())


@pytest.fixture
async def constrained_float_schema(
    db: InfrahubDatabase,
    default_branch: Branch,
    group_schema: None,
    data_schema: None,
) -> SchemaBranch:
    return _register_schema(branch=default_branch, schema_root=_build_constrained_float_schema_root())


@pytest.fixture
async def default_float_schema(
    db: InfrahubDatabase,
    default_branch: Branch,
    group_schema: None,
    data_schema: None,
) -> SchemaBranch:
    return _register_schema(branch=default_branch, schema_root=_build_default_float_schema_root())


# ---------------------------------------------------------------------------
# T010 - Schema loading with Float attribute
# ---------------------------------------------------------------------------


class TestFloatSchemaLoading:
    """Verify that Float attributes are accepted in schemas and registered correctly."""

    async def test_float_attribute_loads(
        self, db: InfrahubDatabase, default_branch: Branch, float_schema: SchemaBranch
    ) -> None:
        schema = registry.schema.get_node_schema(name="TestMeasurement", branch=default_branch)
        weight_attr = schema.get_attribute("weight")
        assert weight_attr.kind == "Float"
        assert weight_attr.optional is False

    async def test_float_attribute_optional(
        self, db: InfrahubDatabase, default_branch: Branch, float_schema: SchemaBranch
    ) -> None:
        schema = registry.schema.get_node_schema(name="TestMeasurement", branch=default_branch)
        height_attr = schema.get_attribute("height")
        assert height_attr.kind == "Float"
        assert height_attr.optional is True

    async def test_float_default_value(
        self, db: InfrahubDatabase, default_branch: Branch, default_float_schema: SchemaBranch
    ) -> None:
        schema = registry.schema.get_node_schema(name="TestDevice", branch=default_branch)
        attr = schema.get_attribute("rack_units")
        assert attr.kind == "Float"
        assert attr.default_value == 1.5

    async def test_float_with_parameters(
        self, db: InfrahubDatabase, default_branch: Branch, constrained_float_schema: SchemaBranch
    ) -> None:
        schema = registry.schema.get_node_schema(name="TestSensor", branch=default_branch)
        attr = schema.get_attribute("temperature")
        assert attr.kind == "Float"
        assert attr.parameters.min_value == -40.0
        assert attr.parameters.max_value == 85.0


# ---------------------------------------------------------------------------
# T011 - Float value storage round-trip
# ---------------------------------------------------------------------------


class TestFloatValueRoundTrip:
    """Store Float values and verify they survive the full create/store/retrieve cycle."""

    async def test_store_and_retrieve_float(
        self, db: InfrahubDatabase, default_branch: Branch, float_schema: SchemaBranch
    ) -> None:
        node = await Node.init(db=db, schema="TestMeasurement", branch=default_branch)
        await node.new(db=db, label="widget-a", weight=7.7)
        await node.save(db=db)

        refreshed = await NodeManager.get_one(db=db, id=node.id, branch=default_branch)
        assert refreshed.weight.value == 7.7

    async def test_store_and_retrieve_1_5(
        self, db: InfrahubDatabase, default_branch: Branch, float_schema: SchemaBranch
    ) -> None:
        node = await Node.init(db=db, schema="TestMeasurement", branch=default_branch)
        await node.new(db=db, label="widget-b", weight=1.5)
        await node.save(db=db)

        refreshed = await NodeManager.get_one(db=db, id=node.id, branch=default_branch)
        assert refreshed.weight.value == 1.5

    async def test_store_integer_as_float(
        self, db: InfrahubDatabase, default_branch: Branch, float_schema: SchemaBranch
    ) -> None:
        node = await Node.init(db=db, schema="TestMeasurement", branch=default_branch)
        await node.new(db=db, label="widget-c", weight=8)
        await node.save(db=db)

        refreshed = await NodeManager.get_one(db=db, id=node.id, branch=default_branch)
        assert refreshed.weight.value == 8.0

    async def test_store_zero(
        self, db: InfrahubDatabase, default_branch: Branch, float_schema: SchemaBranch
    ) -> None:
        node = await Node.init(db=db, schema="TestMeasurement", branch=default_branch)
        await node.new(db=db, label="widget-d", weight=0.0)
        await node.save(db=db)

        refreshed = await NodeManager.get_one(db=db, id=node.id, branch=default_branch)
        assert refreshed.weight.value == 0.0

    async def test_store_negative(
        self, db: InfrahubDatabase, default_branch: Branch, float_schema: SchemaBranch
    ) -> None:
        node = await Node.init(db=db, schema="TestMeasurement", branch=default_branch)
        await node.new(db=db, label="widget-e", weight=-3.14)
        await node.save(db=db)

        refreshed = await NodeManager.get_one(db=db, id=node.id, branch=default_branch)
        assert refreshed.weight.value == -3.14

    async def test_store_default_value(
        self, db: InfrahubDatabase, default_branch: Branch, default_float_schema: SchemaBranch
    ) -> None:
        node = await Node.init(db=db, schema="TestDevice", branch=default_branch)
        await node.new(db=db, label="dev-a")
        await node.save(db=db)

        refreshed = await NodeManager.get_one(db=db, id=node.id, branch=default_branch)
        assert refreshed.rack_units.value == 1.5

    async def test_optional_float_null(
        self, db: InfrahubDatabase, default_branch: Branch, float_schema: SchemaBranch
    ) -> None:
        node = await Node.init(db=db, schema="TestMeasurement", branch=default_branch)
        await node.new(db=db, label="widget-f", weight=1.0, height=None)
        await node.save(db=db)

        refreshed = await NodeManager.get_one(db=db, id=node.id, branch=default_branch)
        assert refreshed.height.value is None


# ---------------------------------------------------------------------------
# T013 - Constraint enforcement at create/update
# ---------------------------------------------------------------------------


class TestFloatConstraintEnforcement:
    """Verify that min_value / max_value constraints are enforced."""

    async def test_value_within_range_accepted(
        self, db: InfrahubDatabase, default_branch: Branch, constrained_float_schema: SchemaBranch
    ) -> None:
        node = await Node.init(db=db, schema="TestSensor", branch=default_branch)
        await node.new(db=db, label="sensor-ok", temperature=22.5)
        await node.save(db=db)

        refreshed = await NodeManager.get_one(db=db, id=node.id, branch=default_branch)
        assert refreshed.temperature.value == 22.5

    async def test_value_below_min_rejected(
        self, db: InfrahubDatabase, default_branch: Branch, constrained_float_schema: SchemaBranch
    ) -> None:
        node = await Node.init(db=db, schema="TestSensor", branch=default_branch)
        with pytest.raises(ValidationError, match="lower than the minimum"):
            await node.new(db=db, label="sensor-cold", temperature=-50.0)

    async def test_value_above_max_rejected(
        self, db: InfrahubDatabase, default_branch: Branch, constrained_float_schema: SchemaBranch
    ) -> None:
        node = await Node.init(db=db, schema="TestSensor", branch=default_branch)
        with pytest.raises(ValidationError, match="higher than the maximum"):
            await node.new(db=db, label="sensor-hot", temperature=100.0)

    async def test_boundary_min_accepted(
        self, db: InfrahubDatabase, default_branch: Branch, constrained_float_schema: SchemaBranch
    ) -> None:
        node = await Node.init(db=db, schema="TestSensor", branch=default_branch)
        await node.new(db=db, label="sensor-min", temperature=-40.0)
        await node.save(db=db)

        refreshed = await NodeManager.get_one(db=db, id=node.id, branch=default_branch)
        assert refreshed.temperature.value == -40.0

    async def test_boundary_max_accepted(
        self, db: InfrahubDatabase, default_branch: Branch, constrained_float_schema: SchemaBranch
    ) -> None:
        node = await Node.init(db=db, schema="TestSensor", branch=default_branch)
        await node.new(db=db, label="sensor-max", temperature=85.0)
        await node.save(db=db)

        refreshed = await NodeManager.get_one(db=db, id=node.id, branch=default_branch)
        assert refreshed.temperature.value == 85.0

    async def test_update_violating_max_rejected(
        self, db: InfrahubDatabase, default_branch: Branch, constrained_float_schema: SchemaBranch
    ) -> None:
        node = await Node.init(db=db, schema="TestSensor", branch=default_branch)
        await node.new(db=db, label="sensor-upd", temperature=50.0)
        await node.save(db=db)

        refreshed = await NodeManager.get_one(db=db, id=node.id, branch=default_branch)
        refreshed.temperature.value = 200.0
        with pytest.raises(ValidationError, match="higher than the maximum"):
            await refreshed.save(db=db)


# ---------------------------------------------------------------------------
# T014 - GraphQL Float filtering
# ---------------------------------------------------------------------------


class TestFloatGraphQLFiltering:
    """Verify that Float attributes can be queried through GraphQL."""

    async def test_filter_by_exact_float_value(
        self, db: InfrahubDatabase, default_branch: Branch, float_schema: SchemaBranch
    ) -> None:
        node1 = await Node.init(db=db, schema="TestMeasurement", branch=default_branch)
        await node1.new(db=db, label="item-1", weight=7.7)
        await node1.save(db=db)

        node2 = await Node.init(db=db, schema="TestMeasurement", branch=default_branch)
        await node2.new(db=db, label="item-2", weight=3.5)
        await node2.save(db=db)

        results = await NodeManager.query(
            db=db, schema="TestMeasurement", branch=default_branch, filters={"weight__value": 7.7}
        )
        assert len(results) == 1
        assert results[0].weight.value == 7.7

    async def test_filter_by_isnull(
        self, db: InfrahubDatabase, default_branch: Branch, float_schema: SchemaBranch
    ) -> None:
        node1 = await Node.init(db=db, schema="TestMeasurement", branch=default_branch)
        await node1.new(db=db, label="with-height", weight=1.0, height=10.5)
        await node1.save(db=db)

        node2 = await Node.init(db=db, schema="TestMeasurement", branch=default_branch)
        await node2.new(db=db, label="no-height", weight=2.0, height=None)
        await node2.save(db=db)

        results_null = await NodeManager.query(
            db=db, schema="TestMeasurement", branch=default_branch, filters={"height__isnull": True}
        )
        labels_null = {r.label.value for r in results_null}
        assert "no-height" in labels_null
        assert "with-height" not in labels_null


# ---------------------------------------------------------------------------
# Fixtures for migration tests (Number <-> Float)
# ---------------------------------------------------------------------------


def _build_number_schema_root() -> SchemaRoot:
    """Schema with a Number (integer) attribute for migration testing."""
    node_schema = {
        "name": "Item",
        "namespace": "Test",
        "default_filter": "label__value",
        "display_labels": ["label__value"],
        "branch": BranchSupportType.AWARE.value,
        "attributes": [
            {"name": "label", "kind": "Text", "unique": True},
            {"name": "quantity", "kind": "Number"},
        ],
    }
    return SchemaRoot(nodes=[NodeSchema(**node_schema)])


@pytest.fixture
async def number_schema(
    db: InfrahubDatabase,
    default_branch: Branch,
    group_schema: None,
    data_schema: None,
) -> SchemaBranch:
    return _register_schema(branch=default_branch, schema_root=_build_number_schema_root())


# ---------------------------------------------------------------------------
# T022 - Number -> Float migration
# ---------------------------------------------------------------------------


class TestNumberFloatMigration:
    """Verify Number->Float kind change succeeds for integers, and Float->Number
    kind change fails when fractional values exist."""

    async def test_number_to_float_succeeds(
        self, db: InfrahubDatabase, default_branch: Branch, number_schema: SchemaBranch
    ) -> None:
        """Integer values like 8 are valid floats, so Number->Float should pass validation."""
        node = await Node.init(db=db, schema="TestItem", branch=default_branch)
        await node.new(db=db, label="item-int", quantity=8)
        await node.save(db=db)

        item_schema = registry.schema.get(name="TestItem")
        qty_attr = item_schema.get_attribute(name="quantity")
        qty_attr.kind = "Float"
        registry.schema.set(name="TestItem", schema=item_schema, branch=default_branch.name)

        schema_path = SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestItem", field_name="quantity")

        query = await AttributeKindUpdateValidatorQuery.init(
            db=db, branch=default_branch, node_schema=item_schema, schema_path=schema_path
        )
        await query.execute(db=db)

        grouped_paths = await query.get_paths()
        all_data_paths = grouped_paths.get_all_data_paths()
        assert len(all_data_paths) == 0

    async def test_float_to_number_fails_with_fractional(
        self, db: InfrahubDatabase, default_branch: Branch, float_schema: SchemaBranch
    ) -> None:
        """A float value like 7.7 cannot be stored as an integer, so Float->Number should flag it."""
        node = await Node.init(db=db, schema="TestMeasurement", branch=default_branch)
        await node.new(db=db, label="frac-item", weight=7.7)
        await node.save(db=db)

        meas_schema = registry.schema.get(name="TestMeasurement")
        weight_attr = meas_schema.get_attribute(name="weight")
        weight_attr.kind = "Number"
        registry.schema.set(name="TestMeasurement", schema=meas_schema, branch=default_branch.name)

        schema_path = SchemaPath(
            path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestMeasurement", field_name="weight"
        )

        query = await AttributeKindUpdateValidatorQuery.init(
            db=db, branch=default_branch, node_schema=meas_schema, schema_path=schema_path
        )
        await query.execute(db=db)

        grouped_paths = await query.get_paths()
        all_data_paths = grouped_paths.get_all_data_paths()
        assert len(all_data_paths) == 1
        assert (
            DataPath(
                branch=default_branch.name,
                path_type=PathType.ATTRIBUTE,
                node_id=node.id,
                kind="TestMeasurement",
                field_name="weight",
                value=7.7,
            )
            in all_data_paths
        )
