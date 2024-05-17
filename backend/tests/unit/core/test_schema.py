from typing import Hashable

import pytest
from pydantic import ValidationError

from infrahub.core import registry
from infrahub.core.constants import BranchSupportType
from infrahub.core.schema import (
    AttributeSchema,
    DropdownChoice,
    NodeSchema,
    RelationshipSchema,
    SchemaRoot,
    core_models,
    internal_schema,
)
from infrahub.database import InfrahubDatabase


def test_schema_root_no_generic():
    FULL_SCHEMA = {
        "nodes": [
            {
                "name": "Criticality",
                "namespace": "Test",
                "default_filter": "name__value",
                "branch": BranchSupportType.AWARE.value,
                "attributes": [
                    {"name": "name", "kind": "Text", "unique": True},
                ],
            }
        ]
    }

    assert SchemaRoot(**FULL_SCHEMA)


def test_node_schema_property_unique_attributes():
    SCHEMA = {
        "name": "Criticality",
        "namespace": "Test",
        "default_filter": "name__value",
        "branch": BranchSupportType.AWARE.value,
        "attributes": [
            {"name": "name", "kind": "Text", "unique": True},
            {"name": "description", "kind": "Text"},
        ],
    }

    schema = NodeSchema(**SCHEMA)
    assert len(schema.unique_attributes) == 1
    assert schema.unique_attributes[0].name == "name"


async def test_node_schema_hashable():
    SCHEMA = {
        "name": "Criticality",
        "namespace": "Test",
        "default_filter": "name__value",
        "branch": BranchSupportType.AWARE.value,
        "attributes": [
            {"name": "name", "kind": "Text", "unique": True},
        ],
        "relationships": [
            {"name": "first", "peer": "TestCriticality", "cardinality": "one"},
            {"name": "second", "identifier": "something_unique", "peer": "TestCriticality", "cardinality": "one"},
        ],
    }
    schema = NodeSchema(**SCHEMA)

    assert isinstance(schema, Hashable)
    assert schema.get_hash()


async def test_attribute_schema_hashable():
    SCHEMA = {"name": "name", "kind": "Text", "unique": True}

    schema = AttributeSchema(**SCHEMA)

    assert isinstance(schema, Hashable)
    assert schema.get_hash()


async def test_relationship_schema_hashable():
    SCHEMA = {"name": "first", "peer": "Criticality", "identifier": "cardinality__peer", "cardinality": "one"}

    schema = RelationshipSchema(**SCHEMA)

    assert isinstance(schema, Hashable)
    assert schema.get_hash()


async def test_node_schema_generate_fields_for_display_label():
    SCHEMA = {
        "name": "Criticality",
        "namespace": "Test",
        "default_filter": "name__value",
        "display_labels": ["name__value", "level__value"],
        "branch": BranchSupportType.AWARE.value,
        "attributes": [
            {"name": "name", "kind": "Text", "unique": True},
            {"name": "level", "kind": "Number"},
        ],
        "relationships": [
            {"name": "first", "peer": "TestCriticality", "cardinality": "one"},
        ],
    }

    schema = NodeSchema(**SCHEMA)
    assert schema.generate_fields_for_display_label() == {"level": {"value": None}, "name": {"value": None}}


async def test_rel_schema_query_filter(db: InfrahubDatabase, default_branch, car_person_schema):
    person = registry.schema.get(name="TestPerson")
    rel = person.relationships[0]

    # Filter relationships by NAME__VALUE
    filters, params, matchs = await rel.get_query_filter(db=db, filter_name="name__value", filter_value="alice")
    expected_response = [
        "(n)",
        "<-[r1:IS_RELATED]-",
        "(rl:Relationship { name: $rel_cars_rel_name })",
        "<-[r2:IS_RELATED]-",
        "(peer:Node)",
        "-[:HAS_ATTRIBUTE]-",
        "(i:Attribute { name: $attr_name_name })",
        "-[:HAS_VALUE]-",
        "(av:AttributeValue { value: $attr_name_value })",
    ]
    assert [str(item) for item in filters] == expected_response
    assert params == {"attr_name_name": "name", "attr_name_value": "alice", "rel_cars_rel_name": "testcar__testperson"}
    assert matchs == []

    # Filter relationship by ID
    filters, params, matchs = await rel.get_query_filter(db=db, name="bob", filter_name="id", filter_value="XXXX-YYYY")
    expected_response = [
        "(n)",
        "<-[r1:IS_RELATED]-",
        "(rl:Relationship { name: $rel_cars_rel_name })",
        "<-[r2:IS_RELATED]-",
        "(peer:Node { uuid: $rel_cars_peer_id })",
    ]
    assert [str(item) for item in filters] == expected_response
    assert params == {"rel_cars_peer_id": "XXXX-YYYY", "rel_cars_rel_name": "testcar__testperson"}
    assert matchs == []


async def test_rel_schema_query_filter_no_value(db: InfrahubDatabase, default_branch, car_person_schema):
    person = registry.schema.get(name="TestPerson")
    rel = person.relationships[0]

    # Filter relationships by NAME__VALUE
    filters, params, matchs = await rel.get_query_filter(db=db, filter_name="name__value")
    expected_response = [
        "(n)",
        "<-[r1:IS_RELATED]-",
        "(rl:Relationship { name: $rel_cars_rel_name })",
        "<-[r2:IS_RELATED]-",
        "(peer:Node)",
        "-[:HAS_ATTRIBUTE]-",
        "(i:Attribute { name: $attr_name_name })",
        "-[:HAS_VALUE]-",
        "(av:AttributeValue)",
    ]
    assert [str(item) for item in filters] == expected_response
    assert params == {"attr_name_name": "name", "rel_cars_rel_name": "testcar__testperson"}
    assert matchs == []

    # Filter relationship by ID
    filters, params, matchs = await rel.get_query_filter(db=db, name="bob", filter_name="id")
    expected_response = [
        "(n)",
        "<-[r1:IS_RELATED]-",
        "(rl:Relationship { name: $rel_cars_rel_name })",
        "<-[r2:IS_RELATED]-",
        "(peer:Node)",
    ]
    assert [str(item) for item in filters] == expected_response
    assert params == {"rel_cars_rel_name": "testcar__testperson"}
    assert matchs == []


def test_core_models():
    assert SchemaRoot(**core_models)


def test_internal_schema():
    assert SchemaRoot(**internal_schema)


async def test_attribute_schema_choices_invalid_kind():
    SCHEMA = {"name": "name", "kind": "Text", "choices": [DropdownChoice(name="active", color="#AAbb0f")]}

    with pytest.raises(ValidationError) as exc:
        AttributeSchema(**SCHEMA)

    assert "Can only specify 'choices' for kind=Dropdown" in str(exc.value)


async def test_attribute_schema_dropdown_missing_choices():
    SCHEMA = {"name": "name", "kind": "Dropdown"}

    with pytest.raises(ValidationError) as exc:
        AttributeSchema(**SCHEMA)

    assert "The property 'choices' is required for kind=Dropdown" in str(exc.value)


def test_dropdown_choice_colors():
    active = DropdownChoice(name="active", color="#AAbb0f")
    assert active.color == "#aabb0f"
    with pytest.raises(ValidationError) as exc:
        DropdownChoice(name="active", color="off-white")

    assert "Color must be a valid HTML color code" in str(exc.value)


def test_dropdown_choice_sort():
    active = DropdownChoice(name="active", color="#AAbb0f")
    passive = DropdownChoice(name="passive", color="#AAbb0f")
    assert active < passive
