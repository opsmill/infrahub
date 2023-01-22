import pytest

from infrahub.core.attribute import String
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.timestamp import Timestamp


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


async def test_base_serialization(session, default_branch, all_attribute_types_schema):

    obj1 = await Node.init(session=session, schema="AllAttributeTypes")
    await obj1.new(session=session, name="obj1", mystring="abc", mybool=False, myint=123, mylist=["1", 2, False])
    await obj1.save(session=session)

    obj2 = await Node.init(session=session, schema="AllAttributeTypes")
    await obj2.new(session=session, name="obj2")
    await obj2.save(session=session)

    obj11 = await NodeManager.get_one(obj1.id, session=session)

    assert obj11.mystring.value == obj1.mystring.value
    assert obj11.mybool.value == obj1.mybool.value
    assert obj11.myint.value == obj1.myint.value
    assert obj11.mylist.value == obj1.mylist.value

    assert isinstance(obj11.mystring.value, str)
    assert isinstance(obj11.mybool.value, bool)
    assert isinstance(obj11.myint.value, int)
    assert isinstance(obj11.mylist.value, list)

    obj12 = await NodeManager.get_one(obj2.id, session=session)
    assert obj12.mystring.value is None
    assert obj12.mybool.value is None
    assert obj12.myint.value is None
    assert obj12.mylist.value is None

    # ------------ update ------------
    obj11.mystring.value = "def"
    obj11.mybool.value = True
    obj11.myint.value = 456
    obj11.mylist.value = [True, 23, "qwerty"]
    await obj11.save(session=session)

    obj13 = await NodeManager.get_one(obj1.id, session=session)

    assert obj13.mystring.value == obj11.mystring.value
    assert obj13.mybool.value == obj11.mybool.value
    assert obj13.myint.value == obj11.myint.value
    assert obj13.mylist.value == obj11.mylist.value
