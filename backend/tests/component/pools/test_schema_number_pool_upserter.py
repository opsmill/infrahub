import pytest

from infrahub.core.constants import NumberPoolType
from infrahub.core.node import Node
from infrahub.core.node.resource_manager.number_pool import CoreNumberPool
from infrahub.core.registry import registry
from infrahub.core.schema import GenericSchema, NodeSchema, SchemaRoot
from infrahub.core.schema.attribute_parameters import NumberPoolParameters
from infrahub.core.schema.attribute_schema import AttributeSchema
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.database import InfrahubDatabase
from infrahub.pools.schema_number_pool_upserter import SchemaNumberPoolUpserter
from tests.helpers.schema.snow import SNOW_INCIDENT, SNOW_REQUEST, SNOW_TASK


async def test_get_existing_number_pool_id_returns_pool_id_from_attribute(
    db: InfrahubDatabase, register_core_models_schema: SchemaBranch
) -> None:
    """Test that get_existing_number_pool_id returns pool_id when set in parameters."""
    # Create a pool manually
    number_pool = await Node.init(db=db, schema="CoreNumberPool", branch=registry.default_branch)
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

    # Create a schema with the pool_id set
    node_schema = NodeSchema(
        name="TestNode",
        namespace="Test",
        include_in_menu=True,
        label="Test Node",
        attributes=[
            AttributeSchema(name="name", kind="Text"),
            AttributeSchema(
                name="number",
                kind="NumberPool",
                optional=False,
                read_only=True,
                unique=True,
                parameters=NumberPoolParameters(
                    start_range=1,
                    end_range=100,
                    number_pool_id=number_pool.id,
                ),
            ),
        ],
    )

    upserter = SchemaNumberPoolUpserter(db=db, schema_manager=registry.schema)
    attribute = node_schema.get_attribute("number")

    pool_id = await upserter.get_existing_number_pool_id(
        schema_node=node_schema,
        attribute=attribute,
        branch_name=registry.default_branch,
    )

    assert pool_id == number_pool.id


async def test_get_existing_number_pool_id_returns_none_when_no_pool(
    db: InfrahubDatabase, register_core_models_schema: SchemaBranch
) -> None:
    """Test that get_existing_number_pool_id returns None when no pool exists."""
    node_schema = NodeSchema(
        name="NewNode",
        namespace="Test",
        include_in_menu=True,
        label="New Node",
        attributes=[
            AttributeSchema(name="name", kind="Text"),
            AttributeSchema(
                name="sequence",
                kind="NumberPool",
                optional=False,
                read_only=True,
                unique=True,
                parameters=NumberPoolParameters(start_range=1, end_range=999),
            ),
        ],
    )

    upserter = SchemaNumberPoolUpserter(db=db, schema_manager=registry.schema)
    attribute = node_schema.get_attribute("sequence")

    pool_id = await upserter.get_existing_number_pool_id(
        schema_node=node_schema,
        attribute=attribute,
        branch_name=registry.default_branch,
    )

    assert pool_id is None


async def test_upsert_number_pool_creates_new_pool(
    db: InfrahubDatabase, register_core_models_schema: SchemaBranch
) -> None:
    """Test that upsert_number_pool creates a new pool when none exists."""
    node_schema = NodeSchema(
        name="NewNode",
        namespace="Test",
        include_in_menu=True,
        label="New Node",
        attributes=[
            AttributeSchema(name="name", kind="Text"),
            AttributeSchema(
                name="sequence",
                kind="NumberPool",
                optional=False,
                read_only=True,
                unique=True,
                parameters=NumberPoolParameters(start_range=10, end_range=99),
            ),
        ],
    )

    upserter = SchemaNumberPoolUpserter(db=db, schema_manager=registry.schema)
    attribute = node_schema.get_attribute("sequence")

    pool = await upserter.upsert_number_pool(
        schema_node=node_schema,
        attribute=attribute,
        branch_name=registry.default_branch,
    )

    assert pool.node.value == "TestNewNode"
    assert pool.node_attribute.value == "sequence"
    assert pool.start_range.value == 10
    assert pool.end_range.value == 99
    assert pool.pool_type.value.value == NumberPoolType.SCHEMA.value


async def test_upsert_number_pool_returns_existing_pool(
    db: InfrahubDatabase, register_core_models_schema: SchemaBranch
) -> None:
    """Test that upsert_number_pool returns existing pool when one exists."""
    node_schema = NodeSchema(
        name="ExistingNode",
        namespace="Test",
        include_in_menu=True,
        label="Existing Node",
        attributes=[
            AttributeSchema(name="name", kind="Text"),
            AttributeSchema(
                name="counter",
                kind="NumberPool",
                optional=False,
                read_only=True,
                unique=True,
                parameters=NumberPoolParameters(start_range=1, end_range=50),
            ),
        ],
    )

    upserter = SchemaNumberPoolUpserter(db=db, schema_manager=registry.schema)
    attribute = node_schema.get_attribute("counter")

    # Create first pool
    pool1 = await upserter.upsert_number_pool(
        schema_node=node_schema,
        attribute=attribute,
        branch_name=registry.default_branch,
    )

    # Request again - should return the same pool
    pool2 = await upserter.upsert_number_pool(
        schema_node=node_schema,
        attribute=attribute,
        branch_name=registry.default_branch,
    )

    assert pool1.id == pool2.id


async def test_upsert_number_pool_with_pool_id_set(
    db: InfrahubDatabase, register_core_models_schema: SchemaBranch
) -> None:
    """Test that upsert_number_pool retrieves pool when pool_id is already set."""
    # Create a pool manually
    number_pool = await Node.init(db=db, schema="CoreNumberPool", branch=registry.default_branch)
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

    # Create a schema with the pool_id set
    node_schema = NodeSchema(
        name="TestNode",
        namespace="Test",
        include_in_menu=True,
        label="Test Node",
        attributes=[
            AttributeSchema(name="name", kind="Text"),
            AttributeSchema(
                name="number",
                kind="NumberPool",
                optional=False,
                read_only=True,
                unique=True,
                parameters=NumberPoolParameters(
                    start_range=1,
                    end_range=100,
                    number_pool_id=number_pool.id,
                ),
            ),
        ],
    )

    upserter = SchemaNumberPoolUpserter(db=db, schema_manager=registry.schema)
    attribute = node_schema.get_attribute("number")

    retrieved_pool = await upserter.upsert_number_pool(
        schema_node=node_schema,
        attribute=attribute,
        branch_name=registry.default_branch,
    )

    assert retrieved_pool.id == number_pool.id


async def test_upsert_number_pool_inherited_uses_generic_kind(
    db: InfrahubDatabase, register_core_models_schema: SchemaBranch
) -> None:
    """Test that upsert_number_pool uses the generic's kind for inherited attributes."""
    # Register the schemas with generics
    schema = SchemaRoot(generics=[SNOW_TASK], nodes=[SNOW_INCIDENT, SNOW_REQUEST])
    schema_branch = registry.schema.register_schema(schema=schema)

    snow_incident = schema_branch.get_node(name="SnowIncident", duplicate=False)
    incident_attr = snow_incident.get_attribute(name="number")

    upserter = SchemaNumberPoolUpserter(db=db, schema_manager=registry.schema)
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

    upserter = SchemaNumberPoolUpserter(db=db, schema_manager=registry.schema)
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
        include_in_menu=True,
        label="Node A",
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
        include_in_menu=True,
        label="Node B",
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

    upserter = SchemaNumberPoolUpserter(db=db, schema_manager=registry.schema)

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
    node_schema = NodeSchema(
        name="TextNode",
        namespace="Test",
        include_in_menu=True,
        label="Text Node",
        attributes=[
            AttributeSchema(name="name", kind="Text"),
        ],
    )

    upserter = SchemaNumberPoolUpserter(db=db, schema_manager=registry.schema)
    attribute = node_schema.get_attribute("name")

    with pytest.raises(ValueError, match="is not a NumberPool type"):
        await upserter.upsert_number_pool(
            schema_node=node_schema,
            attribute=attribute,
            branch_name=registry.default_branch,
        )


async def test_get_inherited_pool_info_returns_none_for_non_node_schema(
    db: InfrahubDatabase, register_core_models_schema: SchemaBranch
) -> None:
    """Test that get_inherited_pool_info returns None for GenericSchema."""
    generic_schema = GenericSchema(
        name="TestGeneric",
        namespace="Test",
        include_in_menu=False,
        label="Test Generic",
        attributes=[
            AttributeSchema(
                name="number",
                kind="NumberPool",
                optional=False,
                read_only=True,
                unique=True,
            ),
        ],
    )

    upserter = SchemaNumberPoolUpserter(db=db, schema_manager=registry.schema)

    result = upserter.get_inherited_pool_info(
        node_schema=generic_schema,
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

    upserter = SchemaNumberPoolUpserter(db=db, schema_manager=registry.schema)

    result = upserter.get_inherited_pool_info(
        node_schema=snow_incident,
        attribute_name="number",
        branch_name=registry.default_branch,
    )

    assert result is not None
    assert result.generic_kind == "SnowTask"
    # pool_id is None because the generic hasn't been assigned a pool yet
    assert result.pool_id is None
