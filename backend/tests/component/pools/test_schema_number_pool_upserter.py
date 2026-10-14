import pytest

from infrahub.core.branch.models import Branch
from infrahub.core.constants import InfrahubKind, NumberPoolType
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.node.resource_manager.number_pool import CoreNumberPool
from infrahub.core.protocols import CoreNumberPoolRange
from infrahub.core.registry import registry
from infrahub.core.schema import GenericSchema, NodeSchema, SchemaRoot
from infrahub.core.schema.attribute_parameters import NumberPoolParameters, NumberPoolRangeParameters
from infrahub.core.schema.attribute_schema import AttributeSchema
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.database import InfrahubDatabase
from infrahub.pools.number_pool_repository import NumberPoolRepository
from infrahub.pools.schema_number_pool_upserter import SchemaNumberPoolUpserter
from tests.component.pools.helpers import NumberPoolRepositoryFailingOnRange
from tests.helpers.schema.snow import SNOW_INCIDENT, SNOW_REQUEST, SNOW_TASK


def number_pool_schema(parameters: NumberPoolParameters) -> NodeSchema:
    return NodeSchema(
        name="Node",
        namespace="Test",
        attributes=[
            AttributeSchema(name="name", kind="Text"),
            AttributeSchema(
                name="number", kind="NumberPool", optional=False, read_only=True, unique=True, parameters=parameters
            ),
        ],
    )


async def pool_ranges(db: InfrahubDatabase, pool_id: str) -> list[tuple[int, int, int | None]]:
    ranges = await NumberPoolRepository(db=db).get_ranges(pool_id=pool_id)
    return [(item.start.value, item.end.value, item.allocation_weight.value) for item in ranges]


@pytest.fixture
def base_schema() -> NodeSchema:
    return number_pool_schema(parameters=NumberPoolParameters(start_range=1, end_range=100))


@pytest.fixture
async def default_number_pool(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> Node:
    number_pool = await Node.init(db=db, schema="CoreNumberPool", branch=default_branch)
    await number_pool.new(
        db=db,
        name="Pre-existing Pool",
        node="TestNode",
        node_attribute="number",
        start_range=1,
        end_range=100,
        pool_type=NumberPoolType.SCHEMA.value,
    )
    await number_pool.save(db=db)
    return number_pool


@pytest.fixture
def schema_with_number_pool_id(default_number_pool: Node, base_schema: NodeSchema) -> NodeSchema:
    number_attr = base_schema.get_attribute("number")
    number_attr.parameters.number_pool_id = default_number_pool.id
    return base_schema


async def test_get_existing_number_pool_id_returns_pool_id_from_attribute(
    db: InfrahubDatabase,
    default_number_pool: Node,
    schema_with_number_pool_id: NodeSchema,
) -> None:
    """Test that get_existing_number_pool_id returns pool_id when set in parameters."""
    upserter = SchemaNumberPoolUpserter(db=db, schema_manager=registry.schema, range_store_factory=NumberPoolRepository)
    attribute = schema_with_number_pool_id.get_attribute("number")

    pool_id = await upserter.get_existing_number_pool_id(
        schema_node=schema_with_number_pool_id,
        attribute=attribute,
        branch_name=registry.default_branch,
    )

    assert pool_id == default_number_pool.id


async def test_get_existing_number_pool_id_returns_none_when_no_pool(
    db: InfrahubDatabase, base_schema: NodeSchema
) -> None:
    """Test that get_existing_number_pool_id returns None when no pool exists."""
    upserter = SchemaNumberPoolUpserter(db=db, schema_manager=registry.schema, range_store_factory=NumberPoolRepository)
    attribute = base_schema.get_attribute("number")

    pool_id = await upserter.get_existing_number_pool_id(
        schema_node=base_schema,
        attribute=attribute,
        branch_name=registry.default_branch,
    )

    assert pool_id is None


async def test_upsert_number_pool_creates_new_pool(
    db: InfrahubDatabase, base_schema: NodeSchema, register_core_models_schema: SchemaBranch
) -> None:
    """Test that upsert_number_pool creates a new pool when none exists."""
    upserter = SchemaNumberPoolUpserter(db=db, schema_manager=registry.schema, range_store_factory=NumberPoolRepository)
    attribute = base_schema.get_attribute("number")

    pool = await upserter.upsert_number_pool(
        schema_node=base_schema,
        attribute=attribute,
        branch_name=registry.default_branch,
    )

    assert pool.node.value == "TestNode"
    assert pool.node_attribute.value == "number"
    assert pool.start_range.value == 1
    assert pool.end_range.value == 100
    assert pool.pool_type.value.value == NumberPoolType.SCHEMA.value


async def test_upsert_number_pool_from_ranges_materialises_weighted_ranges(
    db: InfrahubDatabase, register_core_models_schema: SchemaBranch
) -> None:
    """A declaration listing ranges gives the pool one range node per entry, weights kept."""
    schema = number_pool_schema(
        parameters=NumberPoolParameters(
            ranges=[
                NumberPoolRangeParameters(start=300, end=400),
                NumberPoolRangeParameters(start=100, end=200, weight=10),
            ]
        )
    )

    pool = await SchemaNumberPoolUpserter(
        db=db, schema_manager=registry.schema, range_store_factory=NumberPoolRepository
    ).upsert_number_pool(
        schema_node=schema, attribute=schema.get_attribute("number"), branch_name=registry.default_branch
    )

    assert await pool_ranges(db=db, pool_id=pool.get_id()) == [(100, 200, 10), (300, 400, None)]
    assert (pool.start_range.value, pool.end_range.value) == (None, None)


async def test_upsert_number_pool_from_shorthand_materialises_one_range(
    db: InfrahubDatabase, base_schema: NodeSchema, register_core_models_schema: SchemaBranch
) -> None:
    """The shorthand declaration gives the pool a single range, mirrored back onto the shorthand."""
    pool = await SchemaNumberPoolUpserter(
        db=db, schema_manager=registry.schema, range_store_factory=NumberPoolRepository
    ).upsert_number_pool(
        schema_node=base_schema,
        attribute=base_schema.get_attribute("number"),
        branch_name=registry.default_branch,
    )

    assert await pool_ranges(db=db, pool_id=pool.get_id()) == [(1, 100, None)]
    stored = await NodeManager.get_one(db=db, id=pool.get_id(), branch_agnostic=True)
    assert stored is not None
    assert (stored.get_attribute("start_range").value, stored.get_attribute("end_range").value) == (1, 100)


async def test_upsert_number_pool_without_declared_range_creates_an_empty_pool(
    db: InfrahubDatabase, register_core_models_schema: SchemaBranch
) -> None:
    """A declaration using neither spelling gives a pool holding no range and a null shorthand."""
    schema = number_pool_schema(parameters=NumberPoolParameters())

    pool = await SchemaNumberPoolUpserter(
        db=db, schema_manager=registry.schema, range_store_factory=NumberPoolRepository
    ).upsert_number_pool(
        schema_node=schema, attribute=schema.get_attribute("number"), branch_name=registry.default_branch
    )

    assert await pool_ranges(db=db, pool_id=pool.get_id()) == []
    stored = await NodeManager.get_one(db=db, id=pool.get_id(), branch_agnostic=True)
    assert stored is not None
    assert (stored.get_attribute("start_range").value, stored.get_attribute("end_range").value) == (None, None)


async def test_upsert_number_pool_leaves_nothing_behind_when_a_range_cannot_be_written(
    db: InfrahubDatabase, register_core_models_schema: SchemaBranch
) -> None:
    """A pool is created with every declared range or not at all."""
    schema = number_pool_schema(
        parameters=NumberPoolParameters(
            ranges=[NumberPoolRangeParameters(start=1, end=100), NumberPoolRangeParameters(start=200, end=300)]
        )
    )
    upserter = SchemaNumberPoolUpserter(
        db=db,
        schema_manager=registry.schema,
        range_store_factory=lambda db: NumberPoolRepositoryFailingOnRange(db=db, failing_start=200),
    )

    with pytest.raises(RuntimeError, match="range write failed"):
        await upserter.upsert_number_pool(
            schema_node=schema, attribute=schema.get_attribute("number"), branch_name=registry.default_branch
        )

    pools = await NodeManager.query(
        db=db, schema=InfrahubKind.NUMBERPOOL, filters={"node__value": "TestNode"}, branch_agnostic=True
    )
    assert pools == []
    assert await NodeManager.query(db=db, schema=CoreNumberPoolRange, branch_agnostic=True) == []


async def test_upsert_number_pool_returns_existing_pool(
    db: InfrahubDatabase,
    base_schema: NodeSchema,
    default_number_pool: Node,
) -> None:
    """Test that upsert_number_pool returns existing pool when one exists."""
    upserter = SchemaNumberPoolUpserter(db=db, schema_manager=registry.schema, range_store_factory=NumberPoolRepository)
    attribute = base_schema.get_attribute("number")

    # Create first pool
    pool1 = await upserter.upsert_number_pool(
        schema_node=base_schema,
        attribute=attribute,
        branch_name=registry.default_branch,
    )

    # Request again - should return the same pool
    pool2 = await upserter.upsert_number_pool(
        schema_node=base_schema,
        attribute=attribute,
        branch_name=registry.default_branch,
    )

    assert pool1.id == pool2.id


async def test_upsert_number_pool_with_pool_id_set(
    db: InfrahubDatabase, schema_with_number_pool_id: NodeSchema, default_number_pool: Node
) -> None:
    """Test that upsert_number_pool retrieves pool when pool_id is already set."""
    upserter = SchemaNumberPoolUpserter(db=db, schema_manager=registry.schema, range_store_factory=NumberPoolRepository)
    attribute = schema_with_number_pool_id.get_attribute("number")

    retrieved_pool = await upserter.upsert_number_pool(
        schema_node=schema_with_number_pool_id,
        attribute=attribute,
        branch_name=registry.default_branch,
    )

    assert retrieved_pool.id == default_number_pool.id


async def test_upsert_number_pool_inherited_uses_generic_kind(
    db: InfrahubDatabase, register_core_models_schema: SchemaBranch
) -> None:
    """Test that upsert_number_pool uses the generic's kind for inherited attributes."""
    # Register the schemas with generics
    schema = SchemaRoot(generics=[SNOW_TASK], nodes=[SNOW_INCIDENT, SNOW_REQUEST])
    schema_branch = registry.schema.register_schema(schema=schema)

    snow_incident = schema_branch.get_node(name="SnowIncident", duplicate=False)
    incident_attr = snow_incident.get_attribute(name="number")

    upserter = SchemaNumberPoolUpserter(db=db, schema_manager=registry.schema, range_store_factory=NumberPoolRepository)
    registry.node["CoreNumberPool"] = CoreNumberPool

    pool = await upserter.upsert_number_pool(
        schema_node=snow_incident,
        attribute=incident_attr,
        branch_name=registry.default_branch,
    )

    # Pool should be created for the generic (SnowTask), not the node (SnowIncident)
    assert pool.node.value == "SnowTask"
    assert pool.node_attribute.value == "number"


async def test_upsert_number_pool_inherited_shares_pool(
    db: InfrahubDatabase, register_core_models_schema: SchemaBranch
) -> None:
    """Test that inherited attributes from different nodes share the same pool."""
    schema = SchemaRoot(generics=[SNOW_TASK], nodes=[SNOW_INCIDENT, SNOW_REQUEST])
    schema_branch = registry.schema.register_schema(schema=schema)

    snow_incident = schema_branch.get_node(name="SnowIncident", duplicate=False)
    snow_request = schema_branch.get_node(name="SnowRequest", duplicate=False)
    incident_attr = snow_incident.get_attribute(name="number")
    request_attr = snow_request.get_attribute(name="number")

    upserter = SchemaNumberPoolUpserter(db=db, schema_manager=registry.schema, range_store_factory=NumberPoolRepository)
    registry.node["CoreNumberPool"] = CoreNumberPool

    pool_incident = await upserter.upsert_number_pool(
        schema_node=snow_incident,
        attribute=incident_attr,
        branch_name=registry.default_branch,
    )
    pool_request = await upserter.upsert_number_pool(
        schema_node=snow_request,
        attribute=request_attr,
        branch_name=registry.default_branch,
    )

    # Both should get the same pool (from the generic)
    assert pool_incident.id == pool_request.id
    assert pool_incident.node.value == "SnowTask"


async def test_upsert_number_pool_non_inherited_gets_own_pool(
    db: InfrahubDatabase, register_core_models_schema: SchemaBranch
) -> None:
    """Test that non-inherited attributes get their own pools."""
    generic_schema = GenericSchema(
        name="BaseGeneric",
        namespace="Test",
        include_in_menu=False,
        label="Base Generic",
        attributes=[
            AttributeSchema(name="name", kind="Text"),
        ],
    )
    node_a = NodeSchema(
        name="NodeA",
        namespace="Test",
        inherit_from=["TestBaseGeneric"],
        attributes=[
            AttributeSchema(
                name="counter",
                kind="NumberPool",
                optional=False,
                read_only=True,
                unique=True,
            ),
        ],
    )
    node_b = NodeSchema(
        name="NodeB",
        namespace="Test",
        inherit_from=["TestBaseGeneric"],
        attributes=[
            AttributeSchema(
                name="counter",
                kind="NumberPool",
                optional=False,
                read_only=True,
                unique=True,
            ),
        ],
    )

    schema = SchemaRoot(generics=[generic_schema], nodes=[node_a, node_b])
    schema_branch = registry.schema.register_schema(schema=schema)

    node_a_schema = schema_branch.get_node(name="TestNodeA", duplicate=False)
    node_b_schema = schema_branch.get_node(name="TestNodeB", duplicate=False)
    attr_a = node_a_schema.get_attribute(name="counter")
    attr_b = node_b_schema.get_attribute(name="counter")

    upserter = SchemaNumberPoolUpserter(db=db, schema_manager=registry.schema, range_store_factory=NumberPoolRepository)

    pool_a = await upserter.upsert_number_pool(
        schema_node=node_a_schema,
        attribute=attr_a,
        branch_name=registry.default_branch,
    )
    pool_b = await upserter.upsert_number_pool(
        schema_node=node_b_schema,
        attribute=attr_b,
        branch_name=registry.default_branch,
    )

    # Each node should have its own pool
    assert pool_a.id != pool_b.id
    assert pool_a.node.value == "TestNodeA"
    assert pool_b.node.value == "TestNodeB"


async def test_upsert_number_pool_invalid_type_raises(
    db: InfrahubDatabase, register_core_models_schema: SchemaBranch
) -> None:
    """Test that upsert_number_pool raises ValueError for non-NumberPool attributes."""
    upserter = SchemaNumberPoolUpserter(db=db, schema_manager=registry.schema, range_store_factory=NumberPoolRepository)
    attribute = SNOW_INCIDENT.get_attribute("identifier")

    with pytest.raises(ValueError, match="is not a NumberPool type"):
        await upserter.upsert_number_pool(
            schema_node=SNOW_INCIDENT,
            attribute=attribute,
            branch_name=registry.default_branch,
        )


async def test_get_inherited_pool_info_returns_none_for_non_node_schema(
    db: InfrahubDatabase, register_core_models_schema: SchemaBranch
) -> None:
    """Test that get_inherited_pool_info returns None for GenericSchema."""
    upserter = SchemaNumberPoolUpserter(db=db, schema_manager=registry.schema, range_store_factory=NumberPoolRepository)

    result = upserter.get_inherited_pool_info(
        node_schema=SNOW_TASK,
        attribute_name="number",
        branch_name=registry.default_branch,
    )

    assert result is None


async def test_get_inherited_pool_info_returns_info_for_inherited_attribute(
    db: InfrahubDatabase, register_core_models_schema: SchemaBranch
) -> None:
    """Test that get_inherited_pool_info returns correct info for inherited attributes."""
    schema = SchemaRoot(generics=[SNOW_TASK], nodes=[SNOW_INCIDENT])
    schema_branch = registry.schema.register_schema(schema=schema)

    snow_incident = schema_branch.get_node(name="SnowIncident", duplicate=False)

    upserter = SchemaNumberPoolUpserter(db=db, schema_manager=registry.schema, range_store_factory=NumberPoolRepository)

    result = upserter.get_inherited_pool_info(
        node_schema=snow_incident,
        attribute_name="number",
        branch_name=registry.default_branch,
    )

    assert result is not None
    assert result.generic_kind == "SnowTask"
    # pool_id is None because the generic hasn't been assigned a pool yet
    assert result.pool_id is None
