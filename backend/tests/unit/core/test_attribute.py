import uuid

import pytest

from infrahub.core.attribute import Integer, String
from infrahub.core.branch import Branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.schema import NodeSchema
from infrahub.core.timestamp import Timestamp
from infrahub.exceptions import ValidationError


async def test_init(
    session, default_branch: Branch, criticality_schema: NodeSchema, first_account: Node, second_account: Node
):
    schema = criticality_schema.get_attribute("name")
    attr = String(name="test", schema=schema, branch=default_branch, at=Timestamp(), node=None, data="mystring")

    assert attr.value == "mystring"
    assert attr.source_id is None
    assert attr._source is None

    with pytest.raises(LookupError):
        attr.source

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


async def test_validate_format_string(session, default_branch: Branch, criticality_schema: NodeSchema):
    name_schema = criticality_schema.get_attribute("name")

    String(name="test", schema=name_schema, branch=default_branch, at=Timestamp(), node=None, data="five")

    with pytest.raises(ValidationError):
        String(
            name="test",
            schema=name_schema,
            branch=default_branch,
            at=Timestamp(),
            node=None,
            data=["list", "of", "string"],
        )


async def test_validate_format_integer(session, default_branch: Branch, criticality_schema: NodeSchema):
    level_schema = criticality_schema.get_attribute("level")

    Integer(name="test", schema=level_schema, branch=default_branch, at=Timestamp(), node=None, data=88)

    with pytest.raises(ValidationError):
        Integer(name="test", schema=level_schema, branch=default_branch, at=Timestamp(), node=None, data="notaninteger")


async def test_validate_enum(session, default_branch: Branch, criticality_schema: NodeSchema):
    schema = criticality_schema.get_attribute("name")

    # 1/ there is no enum defined in the schema
    String(name="test", schema=schema, branch=default_branch, at=Timestamp(), node=None, data="five")

    # 2/ enum is defined and a valid value is provided
    schema.enum = ["one", "two", "tree"]
    String(name="test", schema=schema, branch=default_branch, at=Timestamp(), node=None, data="one")

    # 3/ enum is defined and a non-valid value is provided
    with pytest.raises(ValidationError):
        String(name="test", schema=schema, branch=default_branch, at=Timestamp(), node=None, data="five")


async def test_validate_regex(session, default_branch: Branch, criticality_schema: NodeSchema):
    schema = criticality_schema.get_attribute("name")

    # 1/ there is no regex defined in the schema
    String(name="test", schema=schema, branch=default_branch, at=Timestamp(), node=None, data="five222")

    # 2/ a regex is defined and a valid value is provided
    schema.regex = "^[A-Z7-9]+$"
    String(name="test", schema=schema, branch=default_branch, at=Timestamp(), node=None, data="FIVE999")

    # 3/ a regex is defined and a non-valid value is provided
    with pytest.raises(ValidationError):
        String(name="test", schema=schema, branch=default_branch, at=Timestamp(), node=None, data="five222")

    # 4/ An invalid regex is defined
    schema.regex = "^[A-Z7-9"
    with pytest.raises(ValidationError):
        String(name="test", schema=schema, branch=default_branch, at=Timestamp(), node=None, data="FIVE999")


async def test_validate_length(session, default_branch: Branch, criticality_schema: NodeSchema):
    schema = criticality_schema.get_attribute("name")

    # 1/ there is no min_length or max_length defined in the schema
    String(name="test", schema=schema, branch=default_branch, at=Timestamp(), node=None, data="five222")

    # 2/ min_length or max_length are defined and a valid value is provided
    schema.min_length = 5
    schema.max_length = 10
    String(name="test", schema=schema, branch=default_branch, at=Timestamp(), node=None, data="FIVE999")

    # 3/ min_length or max_length are defined and a non-valid value is provided
    with pytest.raises(ValidationError):
        String(name="test", schema=schema, branch=default_branch, at=Timestamp(), node=None, data="two")

    with pytest.raises(ValidationError):
        String(name="test", schema=schema, branch=default_branch, at=Timestamp(), node=None, data="thisstringistoolong")


async def test_node_property_getter(session, default_branch: Branch, criticality_schema):
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


async def test_string_attr_query_filter(session, default_branch: Branch):
    filters, params, matchs = String.get_query_filter(name="description", filter_name="value", filter_value="test")
    expected_response = [
        "(n)",
        "[:HAS_ATTRIBUTE]",
        "(i:Attribute { name: $attr_description_name })",
        "[:HAS_VALUE]",
        "(av:AttributeValue { value: $attr_description_value })",
    ]
    assert [str(item) for item in filters] == expected_response
    assert params == {"attr_description_name": "description", "attr_description_value": "test"}
    assert matchs == []

    filters, params, matchs = String.get_query_filter(
        name="description", filter_name="value", filter_value="test", include_match=False
    )
    expected_response = [
        "[:HAS_ATTRIBUTE]",
        "(i:Attribute { name: $attr_description_name })",
        "[:HAS_VALUE]",
        "(av:AttributeValue { value: $attr_description_value })",
    ]
    assert [str(item) for item in filters] == expected_response
    assert params == {"attr_description_name": "description", "attr_description_value": "test"}
    assert matchs == []


async def test_base_serialization(session, default_branch: Branch, all_attribute_types_schema):
    obj1 = await Node.init(session=session, schema="TestAllAttributeTypes")
    await obj1.new(session=session, name="obj1", mystring="abc", mybool=False, myint=123, mylist=["1", 2, False])
    await obj1.save(session=session)

    obj2 = await Node.init(session=session, schema="TestAllAttributeTypes")
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


async def test_to_graphql(session, default_branch: Branch, criticality_schema, first_account: Node):
    schema = criticality_schema.get_attribute("name")

    attr1 = String(
        id=str(uuid.uuid4()),
        name="test",
        schema=schema,
        branch=default_branch,
        at=Timestamp(),
        node=None,
        data="mystring",
    )
    expected_data = {
        "id": attr1.id,
        "value": "mystring",
    }
    assert await attr1.to_graphql(session=session, fields={"value": None}) == expected_data

    expected_data = {
        "id": attr1.id,
        "is_visible": True,
    }
    assert await attr1.to_graphql(session=session, fields={"id": None, "is_visible": None}) == expected_data

    attr2 = String(
        id=str(uuid.uuid4()),
        name="test",
        schema=schema,
        branch=default_branch,
        at=Timestamp(),
        source=first_account,
        node=None,
        data="mystring",
    )
    expected_data = {
        "id": attr2.id,
        "source": {
            "id": first_account.id,
            "display_label": "First Account",
            "type": "CoreAccount",
        },
        "value": "mystring",
    }
    assert (
        await attr2.to_graphql(session=session, fields={"value": None, "source": {"display_label": None}})
        == expected_data
    )


async def test_to_graphql_no_fields(session, default_branch: Branch, criticality_schema, first_account: Node):
    schema = criticality_schema.get_attribute("name")

    attr1 = String(
        id=str(uuid.uuid4()),
        name="test",
        schema=schema,
        branch=default_branch,
        at=Timestamp(),
        node=None,
        data="mystring",
    )
    expected_data = {
        "__typename": "Text",
        "id": attr1.id,
        "is_protected": False,
        "is_visible": True,
        "owner": None,
        "source": None,
        "updated_at": None,
        "value": "mystring",
    }
    assert await attr1.to_graphql(session=session) == expected_data

    attr2 = String(
        id=str(uuid.uuid4()),
        name="test",
        schema=schema,
        branch=default_branch,
        at=Timestamp(),
        source=first_account,
        node=None,
        data="mystring",
    )
    expected_data = {
        "__typename": "Text",
        "id": attr2.id,
        "is_protected": False,
        "is_visible": True,
        "owner": None,
        "source": {
            "__typename": "CoreAccount",
            "display_label": "First Account",
            "id": first_account.id,
            "type": "CoreAccount",
        },
        "updated_at": None,
        "value": "mystring",
    }
    assert await attr2.to_graphql(session=session) == expected_data
