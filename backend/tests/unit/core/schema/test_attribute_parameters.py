import sys
from copy import deepcopy
from typing import Any

import pydantic
import pytest

from infrahub import config
from infrahub.core.constants import InfrahubKind
from infrahub.core.node import Node
from infrahub.core.node.resource_manager.number_pool import CoreNumberPool
from infrahub.core.registry import registry
from infrahub.core.schema import GenericSchema, NodeSchema, SchemaRoot
from infrahub.core.schema.attribute_parameters import (
    NumberAttributeParameters,
    NumberPoolParameters,
    TextAttributeParameters,
)
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.database import InfrahubDatabase
from infrahub.exceptions import ValidationError
from tests.helpers.schema.snow import SNOW_INCIDENT, SNOW_REQUEST, SNOW_TASK


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


def test_number_pool_assign_from_generics() -> None:
    schema = SchemaRoot(generics=[SNOW_TASK], nodes=[SNOW_INCIDENT, SNOW_REQUEST])
    schema_branch = SchemaBranch(cache={})
    schema_branch.load_schema(schema=schema)
    schema_branch.process()

    snow_incident = schema_branch.get_node(name="SnowIncident", duplicate=False)
    snow_request = schema_branch.get_node(name="SnowRequest", duplicate=False)

    incident_attribute = snow_incident.get_attribute(name="number")
    request_attribute = snow_request.get_attribute(name="number")

    assert isinstance(incident_attribute.parameters, NumberPoolParameters)
    assert isinstance(request_attribute.parameters, NumberPoolParameters)
    assert incident_attribute.parameters.number_pool_id
    assert incident_attribute.parameters.number_pool_id == request_attribute.parameters.number_pool_id


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
