import pytest

from infrahub.core.timestamp import Timestamp
from infrahub.core.attribute import String
from infrahub.core.node import Node


@pytest.mark.skip(reason="Currently not working need to refactor attribute property for Async")
async def test_init(session, default_branch, criticality_schema, first_account, second_account):

    schema = criticality_schema.get_attribute("name")
    attr = String(name="test", schema=schema, branch=default_branch, at=Timestamp(), node=None, data="mystring")

    assert attr.value == "mystring"
    assert hasattr(attr, "source")
    assert attr.source_id is None
    assert attr._source is None

    # initialize with a more complex data structure
    attr = String(
        name="test",
        schema=schema,
        branch=default_branch,
        at=Timestamp(),
        node=None,
        source=first_account,
        data={"value": "mystring", "source": second_account},
    )
    assert attr.value == "mystring"
    assert attr.source_id == second_account.id


async def test_node_property_getter(session, default_branch, criticality_schema):

    schema = criticality_schema.get_attribute("name")
    attr = String(name="test", schema=schema, branch=default_branch, at=Timestamp(), node=None, data="mystring")

    obj1 = await Node.init(session=session, schema=criticality_schema)
    await obj1.new(session=session, name="low", level=4)
    await obj1.save(session=session)

    attr.source = "myuuid"
    assert attr._source is None
    assert attr.source_id == "myuuid"

    attr.owner = "myotheruuid"
    assert attr._owner is None
    assert attr.owner_id == "myotheruuid"

    attr.owner = obj1
    assert attr._owner == obj1
    assert attr.owner_id == obj1.id

    attr.owner = "yetotheruuid"
    assert attr._owner is None
    assert attr.owner_id == "yetotheruuid"


async def test_string_attr_query_filter(session, default_branch):

    filters, params, nbr_rels = String.get_query_filter(name="description")
    assert filters == []
    assert params == {}
    assert nbr_rels == 0

    filters, params, nbr_rels = String.get_query_filter(name="description", filters={"value": "test"})
    expected_response = [
        "MATCH (n)-[r1:HAS_ATTRIBUTE]-(i:Attribute { name: $attr_description_name } )-[r2:HAS_VALUE]-(av { value: $attr_description_value })"
    ]
    assert filters == expected_response
    assert params == {"attr_description_name": "description", "attr_description_value": "test"}
    assert nbr_rels == 2

    filters, params, nbr_rels = String.get_query_filter(name="description", filters={"value": "test"}, rels_offset=2)
    expected_response = [
        "MATCH (n)-[r3:HAS_ATTRIBUTE]-(i:Attribute { name: $attr_description_name } )-[r4:HAS_VALUE]-(av { value: $attr_description_value })"
    ]
    assert filters == expected_response
    assert params == {"attr_description_name": "description", "attr_description_value": "test"}
    assert nbr_rels == 2

    filters, params, nbr_rels = String.get_query_filter(
        name="description", filters={"value": "test"}, include_match=False
    )
    expected_response = [
        "-[r1:HAS_ATTRIBUTE]-(i:Attribute { name: $attr_description_name } )-[r2:HAS_VALUE]-(av { value: $attr_description_value })"
    ]
    assert filters == expected_response
    assert params == {"attr_description_name": "description", "attr_description_value": "test"}
    assert nbr_rels == 2
