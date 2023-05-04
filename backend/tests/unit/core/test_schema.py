from typing import Hashable, List, Optional

import pytest
from deepdiff import DeepDiff
from pydantic.error_wrappers import ValidationError

from infrahub.core import registry
from infrahub.core.schema import (
    AttributeSchema,
    BaseSchemaModel,
    NodeSchema,
    RelationshipSchema,
    SchemaRoot,
    core_models,
    internal_schema,
)


def test_base_schema_model_sorting():
    class MySchema(BaseSchemaModel):
        _sort_by: List[str] = ["first_name", "last_name"]
        first_name: str
        last_name: str

    my_list = [
        MySchema(first_name="John", last_name="Doe"),
        MySchema(first_name="David", last_name="Doe"),
        MySchema(first_name="David", last_name="Smith"),
    ]
    sorted_list = sorted(my_list)

    sorted_names = [(item.first_name, item.last_name) for item in sorted_list]
    assert sorted_names == [("David", "Doe"), ("David", "Smith"), ("John", "Doe")]


def test_base_schema_model_hashing():
    class MySubElement(BaseSchemaModel):
        _sort_by: List[str] = ["name"]
        name: str

    class MyTopElement(BaseSchemaModel):
        _sort_by: List[str] = ["name"]
        name: str
        subs: List[MySubElement]

    node1 = MyTopElement(
        name="node1", subs=[MySubElement(name="orange"), MySubElement(name="apple"), MySubElement(name="coconut")]
    )
    node2 = MyTopElement(
        name="node1", subs=[MySubElement(name="apple"), MySubElement(name="orange"), MySubElement(name="coconut")]
    )

    assert hash(node1) == hash(node2)


def test_base_schema_update():
    class MySubElement(BaseSchemaModel):
        _sort_by: List[str] = ["name"]
        name: str
        value1: Optional[str]
        value2: Optional[int]

    class MyTopElement(BaseSchemaModel):
        _sort_by: List[str] = ["name"]
        name: str
        value1: Optional[str]
        value2: Optional[int]
        value3: List[str]
        subs: List[MySubElement]

    node1 = MyTopElement(
        name="node1",
        value1="first",
        value2=2,
        value3=["one", "two"],
        subs=[MySubElement(name="orange", value1="tochange", value2=22), MySubElement(name="coconut")],
    )
    node2 = MyTopElement(
        name="node1",
        value1="FIRST",
        value3=["one", "three"],
        subs=[MySubElement(name="apple"), MySubElement(name="orange", value1="toreplace")],
    )

    expected_result = {
        "name": "node1",
        "subs": [
            {"name": "coconut", "value1": None, "value2": None},
            {"name": "apple", "value1": None, "value2": None},
            {"name": "orange", "value1": "toreplace", "value2": 22},
        ],
        "value1": "FIRST",
        "value2": 2,
        "value3": ["one", "two", "three"],
    }

    assert DeepDiff(expected_result, node1.update(node2).dict()).to_dict() == {}


def test_schema_root_no_generic():
    FULL_SCHEMA = {
        "nodes": [
            {
                "name": "criticality",
                "kind": "Criticality",
                "default_filter": "name__value",
                "branch": True,
                "attributes": [
                    {"name": "name", "kind": "Text", "unique": True},
                ],
            }
        ]
    }

    assert SchemaRoot(**FULL_SCHEMA)


def test_node_schema_unique_names():
    SCHEMA = {
        "name": "criticality",
        "kind": "Criticality",
        "default_filter": "name__value",
        "branch": True,
        "attributes": [
            {"name": "name", "kind": "Text", "unique": True},
            {"name": "name", "kind": "Text", "unique": True},
        ],
    }

    with pytest.raises(ValidationError) as exc:
        NodeSchema(**SCHEMA)

    assert "Names of attributes and relationships must be unique" in str(exc.value)

    SCHEMA = {
        "name": "criticality",
        "kind": "Criticality",
        "default_filter": "name__value",
        "branch": True,
        "attributes": [
            {"name": "name", "kind": "Text", "unique": True},
            {"name": "dupname", "kind": "Text"},
        ],
        "relationships": [
            {"name": "dupname", "peer": "Criticality", "cardinality": "one"},
        ],
    }

    with pytest.raises(ValidationError) as exc:
        NodeSchema(**SCHEMA)

    assert "Names of attributes and relationships must be unique" in str(exc.value)


def test_node_schema_property_unique_attributes():
    SCHEMA = {
        "name": "criticality",
        "kind": "Criticality",
        "default_filter": "name__value",
        "branch": True,
        "attributes": [
            {"name": "name", "kind": "Text", "unique": True},
            {"name": "description", "kind": "Text"},
        ],
    }

    schema = NodeSchema(**SCHEMA)
    assert len(schema.unique_attributes) == 1
    assert schema.unique_attributes[0].name == "name"


def test_node_schema_unique_identifiers():
    SCHEMA = {
        "name": "criticality",
        "kind": "Criticality",
        "default_filter": "name__value",
        "branch": True,
        "attributes": [
            {"name": "name", "kind": "Text", "unique": True},
        ],
        "relationships": [
            {"name": "first", "peer": "Criticality", "cardinality": "one"},
            {"name": "second", "peer": "Criticality", "cardinality": "one"},
        ],
    }

    with pytest.raises(ValidationError) as exc:
        schema = NodeSchema(**SCHEMA)

    assert "Identifier of relationships must be unique" in str(exc.value)

    SCHEMA = {
        "name": "criticality",
        "kind": "Criticality",
        "default_filter": "name__value",
        "branch": True,
        "attributes": [
            {"name": "name", "kind": "Text", "unique": True},
        ],
        "relationships": [
            {"name": "first", "peer": "Criticality", "cardinality": "one"},
            {"name": "second", "identifier": "something_unique", "peer": "Criticality", "cardinality": "one"},
        ],
    }
    schema = NodeSchema(**SCHEMA)
    assert schema.relationships[0].identifier == "criticality__criticality"
    assert schema.relationships[1].identifier == "something_unique"


async def test_node_schema_hashable():
    SCHEMA = {
        "name": "criticality",
        "kind": "Criticality",
        "default_filter": "name__value",
        "branch": True,
        "attributes": [
            {"name": "name", "kind": "Text", "unique": True},
        ],
        "relationships": [
            {"name": "first", "peer": "Criticality", "cardinality": "one"},
            {"name": "second", "identifier": "something_unique", "peer": "Criticality", "cardinality": "one"},
        ],
    }
    schema = NodeSchema(**SCHEMA)

    assert isinstance(schema, Hashable)
    assert hash(schema)


async def test_attribute_schema_hashable():
    SCHEMA = {"name": "name", "kind": "Text", "unique": True}

    schema = AttributeSchema(**SCHEMA)

    assert isinstance(schema, Hashable)
    assert hash(schema)


async def test_relationship_schema_hashable():
    SCHEMA = {"name": "first", "peer": "Criticality", "identifier": "cardinality__peer", "cardinality": "one"}

    schema = RelationshipSchema(**SCHEMA)

    assert isinstance(schema, Hashable)
    assert hash(schema)


async def test_node_schema_generate_fields_for_display_label():
    SCHEMA = {
        "name": "criticality",
        "kind": "Criticality",
        "default_filter": "name__value",
        "display_labels": ["name__value", "level__value"],
        "branch": True,
        "attributes": [
            {"name": "name", "kind": "Text", "unique": True},
            {"name": "level", "kind": "Number"},
        ],
        "relationships": [
            {"name": "first", "peer": "Criticality", "cardinality": "one"},
        ],
    }

    schema = NodeSchema(**SCHEMA)
    assert schema.generate_fields_for_display_label() == {"level": {"value": None}, "name": {"value": None}}

    SCHEMA["display_labels"] = ["name__value__third"]
    schema = NodeSchema(**SCHEMA)
    with pytest.raises(ValueError):
        schema.generate_fields_for_display_label()


async def test_rel_schema_query_filter(session, default_branch, car_person_schema):
    person = registry.get_schema(name="Person")
    rel = person.relationships[0]

    filters, params, nbr_rels = await rel.get_query_filter(session=session)
    assert filters == []
    assert params == {}
    assert nbr_rels == 0

    # Filter relationships by NAME__VALUE
    filters, params, nbr_rels = await rel.get_query_filter(session=session, filters={"name__value": "alice"})
    expected_response = [
        "MATCH (n)-[r1:IS_RELATED]-(rl:Relationship { name: $rel_cars_rel_name })-[r2:IS_RELATED]-(p:Node)-[r3:HAS_ATTRIBUTE]-(i:Attribute { name: $attr_name_name } )-[r4:HAS_VALUE]-(av { value: $attr_name_value })"
    ]
    assert filters == expected_response
    assert params == {"attr_name_name": "name", "attr_name_value": "alice", "rel_cars_rel_name": "car__person"}
    assert nbr_rels == 4

    # Filter relationship by ID
    filters, params, nbr_rels = await rel.get_query_filter(session=session, name="bob", filters={"id": "XXXX-YYYY"})
    expected_response = [
        "MATCH (n)-[r1:IS_RELATED]-(Relationship { name: $rel_cars_rel_name })-[r2:IS_RELATED]-(p:Node { uuid: $rel_cars_peer_id })"
    ]
    assert filters == expected_response
    assert params == {"rel_cars_peer_id": "XXXX-YYYY", "rel_cars_rel_name": "car__person"}
    assert nbr_rels == 2


def test_core_models():
    assert SchemaRoot(**core_models)


def test_internal_schema():
    assert SchemaRoot(**internal_schema)
