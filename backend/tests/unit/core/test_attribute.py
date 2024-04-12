from enum import Enum

import pytest
from infrahub_sdk import UUIDT

from infrahub import config
from infrahub.core.attribute import URL, Dropdown, Integer, IPHost, IPNetwork, String
from infrahub.core.branch import Branch
from infrahub.core.constants import InfrahubKind
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.schema import AttributeSchema, NodeSchema
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase
from infrahub.exceptions import ValidationError


async def test_init(
    db: InfrahubDatabase,
    default_branch: Branch,
    criticality_schema: NodeSchema,
    first_account: Node,
    second_account: Node,
):
    schema = criticality_schema.get_attribute("name")
    attr = String(name="test", schema=schema, branch=default_branch, at=Timestamp(), node=None, data="mystring")

    assert attr.value == "mystring"
    assert attr.source_id is None
    assert attr._source is None

    with pytest.raises(LookupError):
        _ = attr.source

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


async def test_validate_format_ipnetwork_and_iphost(
    db: InfrahubDatabase, default_branch: Branch, criticality_schema: NodeSchema
):
    schema = criticality_schema.get_attribute("name")

    # 1/ test with prefixlen
    IPHost(name="test", schema=schema, branch=default_branch, at=Timestamp(), node=None, data="192.0.2.0/32")
    IPHost(name="test", schema=schema, branch=default_branch, at=Timestamp(), node=None, data="2001:db8::/128")
    IPNetwork(name="test", schema=schema, branch=default_branch, at=Timestamp(), node=None, data="192.0.2.0/27")
    IPNetwork(name="test", schema=schema, branch=default_branch, at=Timestamp(), node=None, data="2001:db8::/64")

    # 2/ test with netmask
    IPHost(name="test", schema=schema, branch=default_branch, at=Timestamp(), node=None, data="192.0.2.1/255.255.255.0")
    IPNetwork(
        name="test", schema=schema, branch=default_branch, at=Timestamp(), node=None, data="192.0.2.0/255.255.255.0"
    )

    # 3/ test without prefix or mask
    IPHost(name="test", schema=schema, branch=default_branch, at=Timestamp(), node=None, data="192.0.2.1")
    IPHost(name="test", schema=schema, branch=default_branch, at=Timestamp(), node=None, data="2001:db8::")
    IPNetwork(name="test", schema=schema, branch=default_branch, at=Timestamp(), node=None, data="192.0.2.1")
    IPNetwork(name="test", schema=schema, branch=default_branch, at=Timestamp(), node=None, data="2001:db8::")

    with pytest.raises(ValidationError):
        IPHost(name="test", schema=schema, branch=default_branch, at=Timestamp(), node=None, data="192.0.2.0/33")

    with pytest.raises(ValidationError):
        IPHost(
            name="test", schema=schema, branch=default_branch, at=Timestamp(), node=None, data="2001:db8::/ffff:ff00::"
        )

    with pytest.raises(ValidationError):
        IPNetwork(
            name="test", schema=schema, branch=default_branch, at=Timestamp(), node=None, data="192.0.2.1/255.255.255.0"
        )

    with pytest.raises(ValidationError):
        IPNetwork(
            name="test", schema=schema, branch=default_branch, at=Timestamp(), node=None, data="2001:db8::/ffff:ff00::"
        )


async def test_validate_validate_url(db: InfrahubDatabase, default_branch: Branch, criticality_schema: NodeSchema):
    schema = criticality_schema.get_attribute("name")

    assert URL(
        name="test", schema=schema, branch=default_branch, at=Timestamp(), node=None, data="https://api.example.com"
    )
    assert URL(
        name="test", schema=schema, branch=default_branch, at=Timestamp(), node=None, data="ftp://api.example.com"
    )


async def test_validate_iphost_returns(db: InfrahubDatabase, default_branch: Branch, criticality_schema: NodeSchema):
    schema = criticality_schema.get_attribute("name")

    test_ipv4 = IPHost(name="test", schema=schema, branch=default_branch, at=Timestamp(), node=None, data="10.0.2.1/31")
    test_ipv6 = IPHost(
        name="test", schema=schema, branch=default_branch, at=Timestamp(), node=None, data="2001:db8::/32"
    )

    assert test_ipv4.value == "10.0.2.1/31"
    assert test_ipv4.ip == "10.0.2.1"
    assert test_ipv4.hostmask == "0.0.0.1"
    assert test_ipv4.netmask == "255.255.255.254"
    assert test_ipv4.network == "10.0.2.0/31"
    assert test_ipv4.prefixlen == 31
    assert test_ipv4.with_hostmask == "10.0.2.1/0.0.0.1"
    assert test_ipv4.with_netmask == "10.0.2.1/255.255.255.254"
    assert test_ipv4.version == 4
    assert test_ipv4.ip_integer == 167772673
    assert test_ipv4.ip_binary == "00001010000000000000001000000001"
    assert len(test_ipv4.ip_binary) == 32
    assert test_ipv4.to_db() == {
        "binary_address": "00001010000000000000001000000001",
        "is_default": False,
        "prefixlen": 31,
        "value": "10.0.2.1/31",
        "version": 4,
    }

    assert test_ipv6.value == "2001:db8::/32"
    assert test_ipv6.ip == "2001:db8::"
    assert test_ipv6.hostmask == "::ffff:ffff:ffff:ffff:ffff:ffff"
    assert test_ipv6.netmask == "ffff:ffff::"
    assert test_ipv6.network == "2001:db8::/32"
    assert test_ipv6.prefixlen == 32
    assert test_ipv6.with_hostmask == "2001:db8::/::ffff:ffff:ffff:ffff:ffff:ffff"
    assert test_ipv6.with_netmask == "2001:db8::/ffff:ffff::"
    assert test_ipv6.version == 6
    assert test_ipv6.ip_integer == 42540766411282592856903984951653826560
    assert (
        test_ipv6.ip_binary
        == "00100000000000010000110110111000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
    )
    assert len(test_ipv6.ip_binary) == 128

    assert test_ipv6.to_db() == {
        "binary_address": f"0010000000000001000011011011100000000000000000000000000000000000000000000000000000000000{'0' * 40}",
        "is_default": False,
        "prefixlen": 32,
        "value": "2001:db8::/32",
        "version": 6,
    }


async def test_validate_ipnetwork_returns(db: InfrahubDatabase, default_branch: Branch, criticality_schema: NodeSchema):
    schema = criticality_schema.get_attribute("name")

    test_ipv4 = IPNetwork(
        name="test", schema=schema, branch=default_branch, at=Timestamp(), node=None, data="10.0.2.0/31"
    )
    test_ipv6 = IPNetwork(
        name="test", schema=schema, branch=default_branch, at=Timestamp(), node=None, data="2001:db8::/32"
    )

    assert test_ipv4.value == "10.0.2.0/31"
    assert test_ipv4.broadcast_address == "10.0.2.1"
    assert test_ipv4.hostmask == "0.0.0.1"
    assert test_ipv4.netmask == "255.255.255.254"
    assert test_ipv4.prefixlen == 31
    assert test_ipv4.num_addresses == 2
    assert test_ipv4.with_hostmask == "10.0.2.0/0.0.0.1"
    assert test_ipv4.with_netmask == "10.0.2.0/255.255.255.254"
    assert test_ipv4.version == 4
    assert test_ipv4.network_address_integer == 167772672
    assert test_ipv4.network_address_binary == "00001010000000000000001000000000"
    assert len(test_ipv4.network_address_binary) == 32

    assert test_ipv4.to_db() == {
        "binary_address": "00001010000000000000001000000000",
        "is_default": False,
        "num_addresses": 2,
        "prefixlen": 31,
        "value": "10.0.2.0/31",
        "version": 4,
    }

    assert test_ipv6.value == "2001:db8::/32"
    assert test_ipv6.broadcast_address == "2001:db8:ffff:ffff:ffff:ffff:ffff:ffff"
    assert test_ipv6.hostmask == "::ffff:ffff:ffff:ffff:ffff:ffff"
    assert test_ipv6.netmask == "ffff:ffff::"
    assert test_ipv6.prefixlen == 32
    assert test_ipv6.num_addresses == 79228162514264337593543950336
    assert test_ipv6.with_hostmask == "2001:db8::/::ffff:ffff:ffff:ffff:ffff:ffff"
    assert test_ipv6.with_netmask == "2001:db8::/ffff:ffff::"
    assert test_ipv6.version == 6
    assert test_ipv6.network_address_integer == 42540766411282592856903984951653826560
    assert (
        test_ipv6.network_address_binary
        == f"0010000000000001000011011011100000000000000000000000000000000000000000000000000000000000{'0' * 40}"
    )
    assert len(test_ipv6.network_address_binary) == 128

    assert test_ipv6.to_db() == {
        "binary_address": f"0010000000000001000011011011100000000000000000000000000000000000000000000000000000000000{'0' * 40}",
        "is_default": False,
        "num_addresses": 79228162514264337593543950336,
        "prefixlen": 32,
        "value": "2001:db8::/32",
        "version": 6,
    }


async def test_validate_content_dropdown(db: InfrahubDatabase, default_branch: Branch, criticality_schema: NodeSchema):
    schema = criticality_schema.get_attribute("status")
    Dropdown(name="test", schema=schema, branch=default_branch, at=Timestamp(), node=None, data="active")

    with pytest.raises(ValidationError) as exc:
        Dropdown(name="test", schema=schema, branch=default_branch, at=Timestamp(), node=None, data="invalid-choice")
    assert "invalid-choice must be one of" in str(exc.value)


async def test_dropdown_properties(db: InfrahubDatabase, default_branch: Branch, criticality_schema: NodeSchema):
    schema = criticality_schema.get_attribute("status")
    active = Dropdown(name="test", schema=schema, branch=default_branch, at=Timestamp(), node=None, data="active")
    passive = Dropdown(name="test", schema=schema, branch=default_branch, at=Timestamp(), node=None, data="passive")

    assert active.value == "active"
    assert active.description == "Online things"
    assert active.label == "Active"
    # The color of the active choice is hardoced within criticality_schema
    assert active.color == "#00ff00"
    assert passive.value == "passive"
    assert not passive.description
    assert passive.label == "Redundancy nodes not in the active path"
    # The color of the passive choice comes from the color selector in infrahub.visuals
    assert passive.color == "#ed6a5a"


async def test_validate_format_string(db: InfrahubDatabase, default_branch: Branch, criticality_schema: NodeSchema):
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


async def test_validate_format_integer(db: InfrahubDatabase, default_branch: Branch, criticality_schema: NodeSchema):
    level_schema = criticality_schema.get_attribute("level")

    Integer(name="test", schema=level_schema, branch=default_branch, at=Timestamp(), node=None, data=88)

    with pytest.raises(ValidationError):
        Integer(name="test", schema=level_schema, branch=default_branch, at=Timestamp(), node=None, data="notaninteger")


async def test_validate_enum(db: InfrahubDatabase, default_branch: Branch, criticality_schema: NodeSchema):
    schema = criticality_schema.get_attribute("name")

    # 1/ there is no enum defined in the schema
    String(name="test", schema=schema, branch=default_branch, at=Timestamp(), node=None, data="five")

    # 2/ enum is defined and a valid value is provided
    schema.enum = ["one", "two", "tree"]
    String(name="test", schema=schema, branch=default_branch, at=Timestamp(), node=None, data="one")

    # 3/ enum is defined and a non-valid value is provided
    with pytest.raises(ValidationError):
        String(name="test", schema=schema, branch=default_branch, at=Timestamp(), node=None, data="five")


async def test_validate_regex(db: InfrahubDatabase, default_branch: Branch, criticality_schema: NodeSchema):
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


async def test_validate_length(db: InfrahubDatabase, default_branch: Branch, criticality_schema: NodeSchema):
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


async def test_node_property_getter(db: InfrahubDatabase, default_branch: Branch, criticality_schema):
    schema = criticality_schema.get_attribute("name")
    attr = String(name="test", schema=schema, branch=default_branch, at=Timestamp(), node=None, data="mystring")

    obj1 = await Node.init(db=db, schema=criticality_schema)
    await obj1.new(db=db, name="low", level=4)
    await obj1.save(db=db)

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


async def test_get_query_filter_string_value(db: InfrahubDatabase, default_branch: Branch):
    attr_schema = AttributeSchema(name="something", kind="Text")
    filters, params, matchs = await attr_schema.get_query_filter(
        name="description", filter_name="value", filter_value="test"
    )
    expected_response = [
        "(n)",
        "-[:HAS_ATTRIBUTE]-",
        "(i:Attribute { name: $attr_description_name })",
        "-[:HAS_VALUE]-",
        "(av:AttributeValue { value: $attr_description_value })",
    ]
    assert [str(item) for item in filters] == expected_response
    assert params == {"attr_description_name": "description", "attr_description_value": "test"}
    assert matchs == []

    filters, params, matchs = await attr_schema.get_query_filter(
        name="description", filter_name="value", filter_value="test", include_match=False
    )
    expected_response = [
        "-[:HAS_ATTRIBUTE]-",
        "(i:Attribute { name: $attr_description_name })",
        "-[:HAS_VALUE]-",
        "(av:AttributeValue { value: $attr_description_value })",
    ]
    assert [str(item) for item in filters] == expected_response
    assert params == {"attr_description_name": "description", "attr_description_value": "test"}
    assert matchs == []


async def test_get_query_filter_any(db: InfrahubDatabase, default_branch: Branch):
    attr_schema = AttributeSchema(name="something", kind="Text")
    filters, params, matchs = await attr_schema.get_query_filter(name="any", filter_name="value", filter_value="test")
    expected_response = [
        "(n)",
        "-[:HAS_ATTRIBUTE]-",
        "(i:Attribute)",
        "-[:HAS_VALUE]-",
        "(av:AttributeValue { value: $attr_any_value })",
    ]
    assert [str(item) for item in filters] == expected_response
    assert params == {"attr_any_value": "test"}
    assert matchs == []


async def test_get_query_filter_flag_property(db: InfrahubDatabase, default_branch: Branch):
    attr_schema = AttributeSchema(name="something", kind="Text")
    filters, params, matchs = await attr_schema.get_query_filter(
        name="descr", filter_name="is_protected", filter_value=False
    )
    expected_response = [
        "(n)",
        "-[:HAS_ATTRIBUTE]-",
        "(i:Attribute { name: $attr_descr_name })",
        "-[:IS_PROTECTED]-",
        "(ap:Boolean { value: $attr_descr_is_protected })",
    ]
    assert [str(item) for item in filters] == expected_response
    assert params == {"attr_descr_name": "descr", "attr_descr_is_protected": False}
    assert matchs == []


async def test_get_query_filter_any_node_property(db: InfrahubDatabase, default_branch: Branch):
    attr_schema = AttributeSchema(name="something", kind="Text")
    filters, params, matchs = await attr_schema.get_query_filter(
        name="any", filter_name="source__id", filter_value="abcdef"
    )
    expected_response = [
        "(n)",
        "-[:HAS_ATTRIBUTE]-",
        "(i:Attribute)",
        "-[:HAS_SOURCE]-",
        "(ap:Node { uuid: $attr_any_source_id })",
    ]
    assert [str(item) for item in filters] == expected_response
    assert params == {"attr_any_source_id": "abcdef"}
    assert matchs == []


async def test_get_query_filter_multiple_values(db: InfrahubDatabase, default_branch: Branch):
    attr_schema = AttributeSchema(name="something", kind="Text")
    filters, params, matchs = await attr_schema.get_query_filter(
        name="name", filter_name="values", filter_value=["test1", "test2"]
    )
    expected_response = [
        "(n)",
        "-[:HAS_ATTRIBUTE]-",
        "(i:Attribute { name: $attr_name_name })",
        "-[:HAS_VALUE]-",
        "(av:AttributeValue)",
    ]
    assert [str(item) for item in filters] == expected_response
    assert params == {"attr_name_name": "name", "attr_name_value": ["test1", "test2"]}
    assert matchs == ["av.value IN $attr_name_value"]


async def test_query_filter_enum(db: InfrahubDatabase, default_branch: Branch):
    config.SETTINGS.experimental_features.graphql_enums = True

    class ExternalEnum(Enum):
        ALPHA = "thing-one"
        BRAVO = "thing-two"

    attr_schema = AttributeSchema(name="something", kind="Text", enum=["thing-one", "thing-two"])
    filters, params, matchs = await attr_schema.get_query_filter(
        name="name", filter_name="values", filter_value=[ExternalEnum.BRAVO]
    )
    expected_response = [
        "(n)",
        "-[:HAS_ATTRIBUTE]-",
        "(i:Attribute { name: $attr_name_name })",
        "-[:HAS_VALUE]-",
        "(av:AttributeValue)",
    ]
    assert [str(item) for item in filters] == expected_response
    assert params == {"attr_name_name": "name", "attr_name_value": ["thing-two"]}
    assert matchs == ["av.value IN $attr_name_value"]


async def test_get_query_filter_multiple_values_invalid_type(db: InfrahubDatabase, default_branch: Branch):
    attr_schema = AttributeSchema(name="something", kind="Text")
    with pytest.raises(TypeError):
        await attr_schema.get_query_filter(name="name", filter_name="values", filter_value=["test1", 1.0])


async def test_base_serialization(db: InfrahubDatabase, default_branch: Branch, all_attribute_types_schema):
    obj1 = await Node.init(db=db, schema="TestAllAttributeTypes")
    await obj1.new(db=db, name="obj1", mystring="abc", mybool=False, myint=123, mylist=["1", 2, False])
    await obj1.save(db=db)

    obj2 = await Node.init(db=db, schema="TestAllAttributeTypes")
    await obj2.new(db=db, name="obj2")
    await obj2.save(db=db)

    obj11 = await NodeManager.get_one(id=obj1.id, db=db)

    assert obj11.mystring.value == obj1.mystring.value
    assert obj11.mybool.value == obj1.mybool.value
    assert obj11.myint.value == obj1.myint.value
    assert obj11.mylist.value == obj1.mylist.value

    assert isinstance(obj11.mystring.value, str)
    assert isinstance(obj11.mybool.value, bool)
    assert isinstance(obj11.myint.value, int)
    assert isinstance(obj11.mylist.value, list)

    obj12 = await NodeManager.get_one(obj2.id, db=db)
    assert obj12.mystring.value is None
    assert obj12.mybool.value is None
    assert obj12.myint.value is None
    assert obj12.mylist.value is None

    # ------------ update ------------
    obj11.mystring.value = "def"
    obj11.mybool.value = True
    obj11.myint.value = 456
    obj11.mylist.value = [True, 23, "qwerty"]
    await obj11.save(db=db)

    obj13 = await NodeManager.get_one(obj1.id, db=db)

    assert obj13.mystring.value == obj11.mystring.value
    assert obj13.mybool.value == obj11.mybool.value
    assert obj13.myint.value == obj11.myint.value
    assert obj13.mylist.value == obj11.mylist.value


async def test_to_graphql(db: InfrahubDatabase, default_branch: Branch, criticality_schema, first_account: Node):
    schema = criticality_schema.get_attribute("name")

    attr1 = String(
        id=str(UUIDT()),
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
    assert await attr1.to_graphql(db=db, fields={"value": None}) == expected_data

    expected_data = {
        "id": attr1.id,
        "is_visible": True,
    }
    assert await attr1.to_graphql(db=db, fields={"id": None, "is_visible": None}) == expected_data

    attr2 = String(
        id=str(UUIDT()),
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
            "type": InfrahubKind.ACCOUNT,
        },
        "value": "mystring",
    }
    assert await attr2.to_graphql(db=db, fields={"value": None, "source": {"display_label": None}}) == expected_data


async def test_to_graphql_no_fields(
    db: InfrahubDatabase, default_branch: Branch, criticality_schema, first_account: Node
):
    schema = criticality_schema.get_attribute("name")

    attr1 = String(
        id=str(UUIDT()),
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
        "value": "mystring",
    }
    assert await attr1.to_graphql(db=db) == expected_data

    attr2 = String(
        id=str(UUIDT()),
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
            "__typename": InfrahubKind.ACCOUNT,
            "display_label": "First Account",
            "id": first_account.id,
            "type": InfrahubKind.ACCOUNT,
        },
        "value": "mystring",
    }
    assert await attr2.to_graphql(db=db) == expected_data
