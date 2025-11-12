from dataclasses import dataclass

import pytest

from infrahub.core.schema import AttributeSchema, GenericSchema, NodeSchema
from infrahub.core.schema.definitions.core import core_models_mixed


@dataclass
class SchemaNodeTestCase:
    name: str
    schema: NodeSchema | GenericSchema


@dataclass
class SchemaAttributeTestCase:
    name: str
    schema: AttributeSchema


NODE_SCHEMAS = [SchemaNodeTestCase(name=schema.kind, schema=schema) for schema in core_models_mixed["nodes"]]
GENERIC_SCHEMAS = [SchemaNodeTestCase(name=schema.kind, schema=schema) for schema in core_models_mixed["generics"]]

ALL_SCHEMAS = NODE_SCHEMAS + GENERIC_SCHEMAS

NODE_ATTRIBUTE_SCHEMAS = [
    SchemaAttributeTestCase(name=f"{schema.kind}.{attribute.name}", schema=attribute)
    for schema in core_models_mixed["nodes"] + core_models_mixed["generics"]
    for attribute in schema.attributes
]


@pytest.mark.parametrize(
    "test_case",
    [pytest.param(tc, id=tc.name) for tc in ALL_SCHEMAS],
)
async def test_schema_has_node_description(
    test_case: SchemaNodeTestCase,
) -> None:
    assert test_case.schema.description


@pytest.mark.parametrize(
    "test_case",
    [pytest.param(tc, id=tc.name) for tc in NODE_ATTRIBUTE_SCHEMAS],
)
async def test_schema_has_attribute_descriptions(
    test_case: SchemaAttributeTestCase,
) -> None:
    assert test_case.schema.description
