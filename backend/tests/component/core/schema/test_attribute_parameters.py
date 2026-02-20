import sys
from copy import deepcopy
from typing import Any

import pydantic
import pytest

from infrahub import config
from infrahub.core.branch import Branch
from infrahub.core.constants import InfrahubKind, NumberPoolType
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.node.resource_manager.number_pool import CoreNumberPool
from infrahub.core.protocols import CoreNumberPool as CoreNumberPoolProtocol
from infrahub.core.registry import registry
from infrahub.core.schema import GenericSchema, NodeSchema, SchemaRoot
from infrahub.core.schema.attribute_parameters import (
    AttributeParameters,
    ListAttributeParameters,
    NumberAttributeParameters,
    NumberPoolParameters,
    TextAttributeParameters,
)
from infrahub.core.schema.attribute_schema import AttributeSchema
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.database import InfrahubDatabase
from infrahub.exceptions import ValidationError
from infrahub.pools.schema_number_pool_synchronizer import SchemaNumberPoolSynchronizer
from infrahub.pools.schema_number_pool_upserter import SchemaNumberPoolUpserter
from tests.helpers.schema.snow import SNOW_INCIDENT, SNOW_REQUEST, SNOW_TASK


def build_synchronizer(db: InfrahubDatabase) -> SchemaNumberPoolSynchronizer:
    """Helper to build a SchemaNumberPoolSynchronizer with its dependencies."""
    upserter = SchemaNumberPoolUpserter(db=db, schema_manager=registry.schema)
    return SchemaNumberPoolSynchronizer(db=db, schema_manager=registry.schema, upserter=upserter)


def test_number_pool_with_range() -> None:
    node_schema: dict[str, Any] = {
        "name": "NumberAttribute",
        "namespace": "Test",
        "attributes": [
            {"name": "name", "kind": "Text", "unique": True},
            {
                "name": "assigned_number",
                "kind": "NumberPool",
                "optional": False,
                "unique": True,
                "read_only": True,
                "parameters": {"start_range": 1, "end_range": 10},
            },
        ],
    }

    node = NodeSchema(**node_schema)
    assigned_number_attribute = node.get_attribute("assigned_number")
    assert isinstance(assigned_number_attribute.parameters, NumberPoolParameters)


def test_number_pool_invalid_range() -> None:
    node_schema: dict[str, Any] = {
        "name": "NumberAttribute",
        "namespace": "Test",
        "attributes": [
            {"name": "name", "kind": "Text", "unique": True},
            {
                "name": "assigned_number",
                "kind": "NumberPool",
                "optional": False,
                "unique": True,
                "read_only": True,
                "parameters": {"start_range": 30, "end_range": 25},
            },
        ],
    }
    with pytest.raises(pydantic.ValidationError, match="`start_range` can't be less than `end_range`"):
        NodeSchema(**node_schema)


def test_number_pool_get_pool_size() -> None:
    assert NumberPoolParameters(start_range=10, end_range=25).get_pool_size() == 16
    assert NumberPoolParameters(start_range=10).get_pool_size() == sys.maxsize - 9
    assert NumberPoolParameters(end_range=25).get_pool_size() == 25


def test_number_pool_optional() -> None:
    node_schema_definition: dict[str, Any] = {
        "name": "NumberAttribute",
        "namespace": "Test",
        "attributes": [
            {"name": "name", "kind": "Text", "unique": True},
            {
                "name": "assigned_number",
                "kind": "NumberPool",
                "optional": True,
                "unique": True,
                "read_only": True,
                "parameters": {"start_range": 10, "end_range": 25},
            },
        ],
    }
    node_schema = NodeSchema(**node_schema_definition)

    schema = SchemaRoot(nodes=[node_schema])
    schema_branch = SchemaBranch(cache={})
    schema_branch.load_schema(schema=schema)
    with pytest.raises(
        ValidationError, match=r"TestNumberAttribute.assigned_number is a NumberPool it can't be optional"
    ):
        schema_branch.process()


def test_number_pool_read_only() -> None:
    node_schema_definition: dict[str, Any] = {
        "name": "NumberAttribute",
        "namespace": "Test",
        "attributes": [
            {"name": "name", "kind": "Text", "unique": True},
            {
                "name": "assigned_number",
                "kind": "NumberPool",
                "optional": False,
                "unique": True,
                "read_only": False,
                "parameters": {"start_range": 10, "end_range": 25},
            },
        ],
    }
    node_schema = NodeSchema(**node_schema_definition)

    schema = SchemaRoot(nodes=[node_schema])
    schema_branch = SchemaBranch(cache={})
    schema_branch.load_schema(schema=schema)
    with pytest.raises(
        ValidationError, match=r"TestNumberAttribute.assigned_number is a NumberPool it has to be a read_only attribute"
    ):
        schema_branch.process()


def test_number_pool_override_generic() -> None:
    node_schema_definition: dict[str, Any] = {
        "name": "NumberAttribute",
        "namespace": "Test",
        "inherit_from": ["BaseNumberAttribute"],
        "attributes": [
            {"name": "name", "kind": "Text", "unique": True},
            {
                "name": "number",
                "kind": "NumberPool",
                "optional": False,
                "unique": True,
                "read_only": True,
                "parameters": {"start_range": 16, "end_range": 25},
            },
        ],
    }
    node_schema = NodeSchema(**node_schema_definition)
    generic_node_schema_definition: dict[str, Any] = {
        "name": "NumberAttribute",
        "namespace": "Base",
        "attributes": [
            {"name": "name", "kind": "Text", "unique": True},
            {
                "name": "number",
                "kind": "NumberPool",
                "optional": False,
                "unique": True,
                "read_only": True,
                "parameters": {"start_range": 10, "end_range": 25},
            },
        ],
    }
    generic_schema = GenericSchema(**generic_node_schema_definition)

    schema = SchemaRoot(nodes=[node_schema], generics=[generic_schema])
    schema_branch = SchemaBranch(cache={})
    schema_branch.load_schema(schema=schema)
    with pytest.raises(
        ValidationError,
        match=r"Overriding 'TestNumberAttribute.number' NumberPool attribute from generic 'BaseNumberAttribute' is not supported",
    ):
        schema_branch.process()


def test_number_pool_fail_on_multiple_generics() -> None:
    alternate_base = deepcopy(SNOW_TASK)
    alternate_base.name = "OtherTask"
    for index, attribute in enumerate(list(alternate_base.attributes)):
        if attribute.name == "identifier":
            alternate_base.attributes.pop(index)

    modified_incident = deepcopy(SNOW_INCIDENT)

    modified_incident.inherit_from.append("SnowOtherTask")
    schema = SchemaRoot(generics=[SNOW_TASK, alternate_base], nodes=[modified_incident])
    schema_branch = SchemaBranch(cache={})
    schema_branch.load_schema(schema=schema)
    with pytest.raises(
        ValidationError, match=r"SnowIncident.number is a NumberPool inherited from more than one generic"
    ):
        schema_branch.process()


async def test_create_nodes_from_generic_numberpools(
    db: InfrahubDatabase, register_core_models_schema: SchemaBranch
) -> None:
    schema = SchemaRoot(generics=[SNOW_TASK], nodes=[SNOW_INCIDENT, SNOW_REQUEST])
    schema_branch = registry.schema.register_schema(schema=schema)

    snps = build_synchronizer(db)
    await snps.run()

    snow_incident = schema_branch.get_node(name="SnowIncident", duplicate=False)
    incident_attribute = snow_incident.get_attribute(name="number")
    assert isinstance(incident_attribute.parameters, NumberPoolParameters)
    registry.node[InfrahubKind.NUMBERPOOL] = CoreNumberPool

    incident_1 = await Node.init(db=db, schema="SnowIncident")
    await incident_1.new(db=db, title="The first incident")
    await incident_1.save(db=db)

    request_1 = await Node.init(db=db, schema="SnowRequest")
    await request_1.new(db=db, title="The first request")
    await request_1.save(db=db)

    request_2 = await Node.init(db=db, schema="SnowRequest")
    await request_2.new(db=db, title="The second request")
    await request_2.save(db=db)

    incident_2 = await Node.init(db=db, schema="SnowIncident")
    await incident_2.new(db=db, title="The second incident")
    await incident_2.save(db=db)

    assert incident_1.number.value == 1
    assert incident_1.identifier.value == "INC1"
    assert incident_2.number.value == 4
    assert incident_2.identifier.value == "INC4"
    assert request_1.number.value == 2
    assert request_1.identifier.value == "REQ2"
    assert request_2.number.value == 3
    assert request_2.identifier.value == "REQ3"


async def test_synchronizer_assigns_shared_pool_for_inherited_attributes(
    db: InfrahubDatabase, register_core_models_schema: SchemaBranch
) -> None:
    """Test that inherited NumberPool attributes share the same pool after synchronization.

    Given:
      - GenericSchema 'SnowTask' with NumberPool attribute 'number'
      - NodeSchema 'SnowIncident' inherits from 'SnowTask'
      - NodeSchema 'SnowRequest' inherits from 'SnowTask'

    When:
      - SchemaNumberPoolSynchronizer.run() is called

    Then:
      - One pool ID is assigned to the generic
      - Both inheriting nodes share that same pool ID
    """
    schema = SchemaRoot(generics=[SNOW_TASK], nodes=[SNOW_INCIDENT, SNOW_REQUEST])
    schema_branch = registry.schema.register_schema(schema=schema)

    # Before synchronizer runs, pool IDs should be None
    snow_task = schema_branch.get_generic(name="SnowTask", duplicate=False)
    task_attr = snow_task.get_attribute(name="number")
    assert isinstance(task_attr.parameters, NumberPoolParameters)
    assert task_attr.parameters.number_pool_id is None

    # Run the synchronizer
    snps = build_synchronizer(db)
    await snps.run()

    # After synchronizer runs, get the updated schemas
    updated_schema_branch = registry.schema.get_schema_branch(name=registry.default_branch)
    snow_task = updated_schema_branch.get_generic(name="SnowTask", duplicate=False)
    snow_incident = updated_schema_branch.get_node(name="SnowIncident", duplicate=False)
    snow_request = updated_schema_branch.get_node(name="SnowRequest", duplicate=False)

    task_attr = snow_task.get_attribute(name="number")
    incident_attr = snow_incident.get_attribute(name="number")
    request_attr = snow_request.get_attribute(name="number")

    # All should have the same pool ID now
    assert task_attr.parameters.number_pool_id is not None
    assert incident_attr.parameters.number_pool_id is not None
    assert request_attr.parameters.number_pool_id is not None
    assert task_attr.parameters.number_pool_id == incident_attr.parameters.number_pool_id
    assert task_attr.parameters.number_pool_id == request_attr.parameters.number_pool_id

    # Verify the CoreNumberPool was created with correct node and node_attribute
    pool_id = task_attr.parameters.number_pool_id
    pools = await NodeManager.query(
        db=db,
        schema=CoreNumberPoolProtocol,
        filters={"id": pool_id},
    )
    assert len(pools) == 1
    pool = pools[0]
    # Pool should reference the generic (where the attribute is defined), not the inheriting nodes
    assert pool.node.value == "SnowTask"
    assert pool.node_attribute.value == "number"
    assert pool.pool_type.value.value == NumberPoolType.SCHEMA.value


async def test_synchronizer_assigns_separate_pools_for_non_inherited_attributes(
    db: InfrahubDatabase, register_core_models_schema: SchemaBranch
) -> None:
    """Test that non-inherited NumberPool attributes with the same name get separate pools.

    Given:
      - GenericSchema 'TestGeneric' (no NumberPool attribute)
      - NodeSchema 'TestNodeA' inherits from 'TestGeneric', has NumberPool 'sequence_num'
      - NodeSchema 'TestNodeB' inherits from 'TestGeneric', has NumberPool 'sequence_num'

    When:
      - SchemaNumberPoolSynchronizer.run() is called

    Then:
      - Two separate pools are created (one per node)
      - Each node has its own independent pool ID
    """
    # Create schemas with same-named NumberPool on sibling nodes (not inherited)
    generic_schema = GenericSchema(
        name="TestGeneric",
        namespace="Test",
        include_in_menu=False,
        label="Test Generic",
        attributes=[
            AttributeSchema(name="name", kind="Text", unique=True),
        ],
    )
    node_a_schema = NodeSchema(
        name="NodeA",
        namespace="Test",
        inherit_from=["TestTestGeneric"],
        include_in_menu=True,
        label="Node A",
        attributes=[
            AttributeSchema(
                name="sequence_num",
                kind="NumberPool",
                optional=False,
                read_only=True,
                unique=True,
            ),
        ],
    )
    node_b_schema = NodeSchema(
        name="NodeB",
        namespace="Test",
        inherit_from=["TestTestGeneric"],
        include_in_menu=True,
        label="Node B",
        attributes=[
            AttributeSchema(
                name="sequence_num",
                kind="NumberPool",
                optional=False,
                read_only=True,
                unique=True,
            ),
        ],
    )

    schema = SchemaRoot(generics=[generic_schema], nodes=[node_a_schema, node_b_schema])
    registry.schema.register_schema(schema=schema)

    # Run the synchronizer
    snps = build_synchronizer(db)
    await snps.run()

    # After synchronizer runs, get the updated schemas
    updated_schema_branch = registry.schema.get_schema_branch(name=registry.default_branch)
    node_a = updated_schema_branch.get_node(name="TestNodeA", duplicate=False)
    node_b = updated_schema_branch.get_node(name="TestNodeB", duplicate=False)

    node_a_attr = node_a.get_attribute(name="sequence_num")
    node_b_attr = node_b.get_attribute(name="sequence_num")

    # Both should have pool IDs, but they should be DIFFERENT
    assert node_a_attr.parameters.number_pool_id is not None
    assert node_b_attr.parameters.number_pool_id is not None
    assert node_a_attr.parameters.number_pool_id != node_b_attr.parameters.number_pool_id

    # Verify the CoreNumberPools were created with correct node and node_attribute values
    pool_a = await NodeManager.get_one(db=db, id=node_a_attr.parameters.number_pool_id)
    pool_b = await NodeManager.get_one(db=db, id=node_b_attr.parameters.number_pool_id)

    # Each pool should reference its respective node (not inherited, so each node has its own pool)
    assert pool_a.get_attribute("node").value == "TestNodeA"
    assert pool_a.get_attribute("node_attribute").value == "sequence_num"
    assert pool_a.get_attribute("pool_type").value.value == NumberPoolType.SCHEMA.value

    assert pool_b.get_attribute("node").value == "TestNodeB"
    assert pool_b.get_attribute("node_attribute").value == "sequence_num"
    assert pool_b.get_attribute("pool_type").value.value == NumberPoolType.SCHEMA.value


def test_validate_min_max_number_attribute() -> None:
    with pytest.raises(
        pydantic.ValidationError,
        match="`max_value` can't be less than `min_value` when the schema is configured with strict mode",
    ):
        NumberAttributeParameters(min_value=10, max_value=5)

    assert config.SETTINGS.main.schema_strict_mode


def test_validate_min_max_text_attribute() -> None:
    with pytest.raises(
        pydantic.ValidationError,
        match="`max_length` can't be less than `min_length` when the schema is configured with strict mode",
    ):
        TextAttributeParameters(min_length=10, max_length=5)

    assert config.SETTINGS.main.schema_strict_mode


def test_convert_from_text_to_number_parameters() -> None:
    """Test converting TextAttributeParameters to NumberAttributeParameters."""
    text_params = TextAttributeParameters(regex="^[a-z]+$", min_length=1, max_length=10)
    number_params = NumberAttributeParameters.convert_from(text_params)

    # Should create a valid NumberAttributeParameters with default values
    assert isinstance(number_params, NumberAttributeParameters)
    assert number_params.min_value is None
    assert number_params.max_value is None
    assert number_params.excluded_values is None


def test_convert_from_number_to_text_parameters() -> None:
    """Test converting NumberAttributeParameters to TextAttributeParameters."""
    number_params = NumberAttributeParameters(min_value=0, max_value=100)
    text_params = TextAttributeParameters.convert_from(number_params)

    # Should create a valid TextAttributeParameters with default values
    assert isinstance(text_params, TextAttributeParameters)
    assert text_params.regex is None
    assert text_params.min_length is None
    assert text_params.max_length is None


def test_convert_from_to_base_parameters() -> None:
    """Test converting to base AttributeParameters class."""
    text_params = TextAttributeParameters(regex="test", min_length=5)
    base_params = AttributeParameters.convert_from(text_params)
    assert isinstance(base_params, AttributeParameters)


def test_convert_from_same_class() -> None:
    """Test converting from the same class type preserves values."""
    text_params = TextAttributeParameters(regex="test", min_length=5, max_length=20)
    converted = TextAttributeParameters.convert_from(text_params)

    assert isinstance(converted, TextAttributeParameters)
    assert converted.regex == "test"
    assert converted.min_length == 5
    assert converted.max_length == 20


def test_convert_from_number_pool_to_number_parameters() -> None:
    """Test converting NumberPoolParameters to NumberAttributeParameters."""
    pool_params = NumberPoolParameters(start_range=10, end_range=100)
    number_params = NumberAttributeParameters.convert_from(pool_params)

    assert isinstance(number_params, NumberAttributeParameters)
    assert number_params.min_value is None
    assert number_params.max_value is None


def test_attribute_schema_kind_change_text_to_number() -> None:
    """Test that changing AttributeSchema kind from Text to Number handles parameters."""
    # Create a Text attribute with parameters
    text_attr = AttributeSchema(
        name="test_attr",
        kind="Text",
        parameters=TextAttributeParameters(regex="^[a-z]+$", min_length=1, max_length=10),
    )

    # Create a Number attribute by modifying the kind in the dumped data
    # This simulates what happens during schema updates
    attr_data = text_attr.model_dump()
    attr_data["kind"] = "Number"

    # This should not raise an error about extra fields
    number_attr = AttributeSchema(**attr_data)

    assert number_attr.kind == "Number"
    assert isinstance(number_attr.parameters, NumberAttributeParameters)
    # Parameters should have default values since fields don't overlap
    assert number_attr.parameters.min_value is None
    assert number_attr.parameters.max_value is None


def test_attribute_schema_kind_change_number_to_text() -> None:
    """Test that changing AttributeSchema kind from Number to Text handles parameters."""
    # Create a Number attribute with parameters
    number_attr = AttributeSchema(
        name="test_attr",
        kind="Number",
        parameters=NumberAttributeParameters(min_value=0, max_value=100),
    )

    # Create a Text attribute by modifying the kind in the dumped data
    attr_data = number_attr.model_dump()
    attr_data["kind"] = "Text"

    # This should not raise an error about extra fields
    text_attr = AttributeSchema(**attr_data)

    assert text_attr.kind == "Text"
    assert isinstance(text_attr.parameters, TextAttributeParameters)
    # Parameters should have default values since fields don't overlap
    assert text_attr.parameters.regex is None
    assert text_attr.parameters.min_length is None
    assert text_attr.parameters.max_length is None


def test_attribute_schema_kind_change_with_parameters_object() -> None:
    """Test kind change when AttributeParameters object is passed directly (not dict)."""
    text_params = TextAttributeParameters(regex="test")

    # This simulates a case where parameters is an object (not a dict) and kind doesn't match
    # The validator should handle this by using convert_from
    number_attr = AttributeSchema(
        name="test_attr",
        kind="Number",
        parameters=text_params,
    )

    assert number_attr.kind == "Number"
    assert isinstance(number_attr.parameters, NumberAttributeParameters)


def test_list_attribute_with_regex_parameter() -> None:
    node_schema: dict[str, Any] = {
        "name": "Node",
        "namespace": "Testing",
        "attributes": [
            {"name": "name", "kind": "Text"},
            {
                "name": "protocols",
                "kind": "List",
                "optional": True,
                "parameters": {"regex": "ssh|ping|telnet"},
            },
        ],
    }

    node = NodeSchema(**node_schema)
    protocols_attribute = node.get_attribute("protocols")
    assert isinstance(protocols_attribute.parameters, ListAttributeParameters)
    assert protocols_attribute.parameters.regex == "ssh|ping|telnet"
    assert protocols_attribute.get_regex() == "ssh|ping|telnet"


async def test_list_attribute_regex_parameter_validation(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> None:
    """Test that list values are validated against regex defined in parameters."""
    node_schema: dict[str, Any] = {
        "name": "Node",
        "namespace": "Testing",
        "attributes": [
            {"name": "name", "kind": "Text"},
            {
                "name": "protocols",
                "kind": "List",
                "optional": True,
                "parameters": {"regex": "^(ssh|ping|telnet)$"},
            },
        ],
    }

    schema = NodeSchema(**node_schema)

    # Valid values should work
    node = await Node.init(db=db, schema=schema)
    await node.new(db=db, name="test-node", protocols=["ssh", "ping"])
    assert node.protocols.value == ["ssh", "ping"]

    # Invalid value should raise ValidationError
    invalid_node = await Node.init(db=db, schema=schema)
    with pytest.raises(ValidationError, match=r"http must conform with the regex"):
        await invalid_node.new(db=db, name="test-invalid", protocols=["ssh", "http"])

    # Single invalid value should also fail
    another_node = await Node.init(db=db, schema=schema)
    with pytest.raises(ValidationError, match=r"ftp must conform with the regex"):
        await another_node.new(db=db, name="test-single", protocols=["ftp"])
