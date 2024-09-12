import pytest
from graphql import graphql

from infrahub import config
from infrahub.core import registry
from infrahub.core.constants import InfrahubKind
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.database import InfrahubDatabase
from infrahub.graphql import prepare_graphql_params


async def test_create_simple_object(db: InfrahubDatabase, default_branch, car_person_schema):
    query = """
    mutation {
        TestPersonCreate(data: {name: { value: "John"}, height: {value: 182}}) {
            ok
            object {
                id
            }
        }
    }
    """
    gql_params = prepare_graphql_params(db=db, include_subscription=False, branch=default_branch)
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert result.data["TestPersonCreate"]["ok"] is True

    person_id = result.data["TestPersonCreate"]["object"]["id"]
    assert len(person_id) == 36  # length of an UUID

    person = await NodeManager.get_one(db=db, id=person_id)
    assert person.name.is_default is False
    assert person.height.is_default is False


async def test_create_simple_object_with_ok_return(db: InfrahubDatabase, default_branch, car_person_schema):
    query = """
    mutation {
        TestPersonCreate(data: {name: { value: "John"}, height: {value: 182}}) {
            ok
        }
    }
    """
    gql_params = prepare_graphql_params(db=db, include_subscription=False, branch=default_branch)
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )
    assert result.errors is None
    assert result.data["TestPersonCreate"]["ok"] is True


@pytest.mark.parametrize(
    "graphql_enums_on,enum_value,response_value", [(True, "MANUAL", "MANUAL"), (False, '"manual"', "manual")]
)
async def test_create_simple_object_with_enum(
    db: InfrahubDatabase,
    default_branch,
    person_john_main,
    car_person_schema,
    graphql_enums_on,
    enum_value,
    response_value,
):
    config.SETTINGS.experimental_features.graphql_enums = graphql_enums_on
    query = """
    mutation {
        TestCarCreate(data: {
                name: { value: "JetTricycle"},
                nbr_seats: { value: 1 },
                is_electric: { value: false },
                transmission: { value: %s },
                owner: { id: "John" }
            }) {
            ok
            object {
                id
                transmission {
                    value
                }
            }
        }
    }
    """ % (enum_value)
    gql_params = prepare_graphql_params(db=db, include_subscription=False, branch=default_branch)
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert result.data["TestCarCreate"]["ok"] is True
    assert result.data["TestCarCreate"]["object"]["transmission"]["value"] == response_value

    car_id = result.data["TestCarCreate"]["object"]["id"]
    database_car = await NodeManager.get_one(db=db, id=car_id)
    assert database_car.transmission.value.value == "manual"


async def test_create_enum_when_enums_off_fails(
    db: InfrahubDatabase,
    default_branch,
    person_john_main,
    car_person_schema,
):
    config.SETTINGS.experimental_features.graphql_enums = False
    query = """
    mutation {
        TestCarCreate(data: {
                name: { value: "JetTricycle"},
                nbr_seats: { value: 1 },
                is_electric: { value: false },
                transmission: { value: MANUAL },
                owner: { id: "John" }
            }) {
            ok
            object {
                id
                transmission {
                    value
                }
            }
        }
    }
    """
    gql_params = prepare_graphql_params(db=db, include_subscription=False, branch=default_branch)
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert len(result.errors) == 1
    assert "String cannot represent a non string value" in result.errors[0].message


async def test_create_string_when_enums_on_fails(
    db: InfrahubDatabase,
    default_branch,
    person_john_main,
    car_person_schema,
):
    config.SETTINGS.experimental_features.graphql_enums = True
    query = """
    mutation {
        TestCarCreate(data: {
                name: { value: "JetTricycle"},
                nbr_seats: { value: 1 },
                is_electric: { value: false },
                transmission: { value: "manual" },
                owner: { id: "John" }
            }) {
            ok
            object {
                id
                transmission {
                    value
                }
            }
        }
    }
    """
    gql_params = prepare_graphql_params(db=db, include_subscription=False, branch=default_branch)
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert len(result.errors) == 1
    assert "'TestCarTransmissionValue' cannot represent non-enum value" in result.errors[0].message


async def test_create_with_id(db: InfrahubDatabase, default_branch, car_person_schema):
    uuid1 = "79c83773-6b23-4537-a3ce-b214b625ff1d"
    query = (
        """
    mutation {
        TestPersonCreate(data: {id: "%s", name: { value: "John"}, height: {value: 182}}) {
            ok
            object {
                id
            }
        }
    }
    """
        % uuid1
    )
    gql_params = prepare_graphql_params(db=db, include_subscription=False, branch=default_branch)
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert result.data["TestPersonCreate"]["ok"] is True
    assert result.data["TestPersonCreate"]["object"]["id"] == uuid1

    query = """
    mutation {
        TestPersonCreate(data: {id: "not-valid", name: { value: "John"}, height: {value: 182}}) {
            ok
            object {
                id
            }
        }
    }
    """
    gql_params = prepare_graphql_params(db=db, include_subscription=False, branch=default_branch)
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert result.errors
    assert len(result.errors) == 1
    assert "not-valid is not a valid UUID" in result.errors[0].message


async def test_create_check_unique(db: InfrahubDatabase, default_branch, car_person_schema):
    p1 = await Node.init(db=db, schema="TestPerson")
    await p1.new(db=db, name="John", height=180)
    await p1.save(db=db)

    query = """
    mutation {
        TestPersonCreate(data: {name: { value: "John"}, height: {value: 182}}) {
            ok
            object {
                id
            }
        }
    }
    """
    gql_params = prepare_graphql_params(db=db, include_subscription=False, branch=default_branch)
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert result.errors
    assert len(result.errors) == 1
    assert "An object already exist" in result.errors[0].message


async def test_create_check_unique_across_branch(db: InfrahubDatabase, default_branch, car_person_schema):
    p1 = await Node.init(db=db, schema="TestPerson")
    await p1.new(db=db, name="John", height=180)
    await p1.save(db=db)

    query = """
    mutation {
        TestPersonCreate(data: {name: { value: "John"}, height: {value: 182}}) {
            ok
            object {
                id
            }
        }
    }
    """

    branch1 = await create_branch(branch_name="branch1", db=db)

    gql_params = prepare_graphql_params(db=db, include_subscription=False, branch=branch1)
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert result.errors
    assert len(result.errors) == 1
    assert "An object already exist" in result.errors[0].message


async def test_create_check_unique_in_branch(db: InfrahubDatabase, default_branch, car_person_schema):
    branch1 = await create_branch(branch_name="branch1", db=db)

    p1 = await Node.init(db=db, schema="TestPerson", branch=branch1)
    await p1.new(db=db, name="John", height=180)
    await p1.save(db=db)

    query = """
    mutation {
        TestPersonCreate(data: {name: { value: "John"}, height: {value: 182}}) {
            ok
            object {
                id
            }
        }
    }
    """
    gql_params = prepare_graphql_params(db=db, include_subscription=False, branch=branch1)
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert result.errors
    assert len(result.errors) == 1
    assert "An object already exist" in result.errors[0].message


async def test_all_attributes(db: InfrahubDatabase, default_branch, all_attribute_types_schema):
    query = """
    mutation {
        TestAllAttributeTypesCreate(
            data: {
                name: { value: "obj1" }
                mystring: { value: "abc" }
                mybool: { value: false }
                myint: { value: 123 }
                mylist: { value: [ "1", 2, false ] }
                ipaddress: { value: "10.3.4.254/24" }
                prefix: { value: "10.3.4.0/24" }
            }
        ){
            ok
            object {
                id
            }
        }
    }
    """
    gql_params = prepare_graphql_params(db=db, include_subscription=False, branch=default_branch)
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert result.data["TestAllAttributeTypesCreate"]["ok"] is True
    assert len(result.data["TestAllAttributeTypesCreate"]["object"]["id"]) == 36  # length of an UUID

    objs = await NodeManager.query(db=db, schema="TestAllAttributeTypes")
    obj1 = objs[0]

    assert obj1.mystring.value == "abc"
    assert obj1.mystring.is_default is False
    assert obj1.mybool.value is False
    assert obj1.mybool.is_default is False
    assert obj1.myint.value == 123
    assert obj1.myint.is_default is False
    assert obj1.mylist.value == ["1", 2, False]
    assert obj1.mylist.is_default is False
    assert obj1.ipaddress.value == "10.3.4.254/24"
    assert obj1.ipaddress.is_default is False
    assert obj1.prefix.value == "10.3.4.0/24"
    assert obj1.prefix.is_default is False


async def test_all_attributes_default_value(db: InfrahubDatabase, default_branch, all_attribute_default_types_schema):
    query = """
    mutation {
        TestAllAttributeTypesCreate(
            data: {
                name: { value: "obj1" }
                mystring: { value: "abc" }
                mybool: { value: false }
                myint: { value: 123 }
                mylist: { value: [ "1", 2, false ] }
            }
        ){
            ok
            object {
                id
            }
        }
    }
    """
    gql_params = prepare_graphql_params(db=db, include_subscription=False, branch=default_branch)
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert result.data["TestAllAttributeTypesCreate"]["ok"] is True
    obj_id = result.data["TestAllAttributeTypesCreate"]["object"]["id"]
    assert len(obj_id) == 36  # length of an UUID

    obj1 = await NodeManager.get_one(db=db, id=obj_id)

    assert obj1.mystring.value == "abc"
    assert obj1.mystring.is_default is False
    assert obj1.mybool.value is False
    assert obj1.mybool.is_default is False
    assert obj1.myint.value == 123
    assert obj1.myint.is_default is False
    assert obj1.mylist.value == ["1", 2, False]
    assert obj1.mylist.is_default is False

    assert obj1.mystring_default.value == "a string"
    assert obj1.mystring_default.is_default is True
    assert obj1.mybool_default.value is False
    assert obj1.mybool_default.is_default is True
    assert obj1.myint_default.value == 10
    assert obj1.myint_default.is_default is True
    assert obj1.mylist_default.value == [10, 11, 12]
    assert obj1.mylist_default.is_default is True

    assert obj1.mystring_none.value is None
    assert obj1.mystring_none.is_default is True
    assert obj1.mybool_none.value is None
    assert obj1.mybool_none.is_default is True
    assert obj1.myint_none.value is None
    assert obj1.myint_none.is_default is True
    assert obj1.mylist_none.value is None
    assert obj1.mylist_none.is_default is True


async def test_create_object_with_flag_property(db: InfrahubDatabase, default_branch, car_person_schema):
    query = """
    mutation {
        TestPersonCreate(
            data: {
                name: { value: "John", is_protected: true }
                height: { value: 182, is_visible: false }
            }
        ) {
            ok
            object {
                id
            }
        }
    }
    """
    gql_params = prepare_graphql_params(db=db, include_subscription=False, branch=default_branch)
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert result.data["TestPersonCreate"]["ok"] is True
    assert len(result.data["TestPersonCreate"]["object"]["id"]) == 36  # length of an UUID

    # Query the newly created Node to ensure everything is as expected
    query = """
        query {
            TestPerson {
                edges {
                    node {
                        id
                        name {
                            value
                            is_protected
                        }
                        height {
                            is_visible
                        }
                    }
                }
            }
        }
    """
    gql_params = prepare_graphql_params(db=db, include_subscription=False, branch=default_branch)
    result1 = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert result1.errors is None
    assert result1.data["TestPerson"]["edges"][0]["node"]["name"]["is_protected"] is True
    assert result1.data["TestPerson"]["edges"][0]["node"]["height"]["is_visible"] is False


async def test_create_object_with_node_property(
    db: InfrahubDatabase, default_branch, car_person_schema, first_account, second_account
):
    query = """
    mutation {
        TestPersonCreate(
            data: {
                name: { value: "John", source: "%s" }
                height: { value: 182, owner: "%s" }
            }
        ) {
            ok
            object {
                id
            }
        }
    }
    """ % (
        first_account.id,
        second_account.id,
    )

    gql_params = prepare_graphql_params(db=db, include_subscription=False, branch=default_branch)
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert result.data["TestPersonCreate"]["ok"] is True
    assert len(result.data["TestPersonCreate"]["object"]["id"]) == 36  # length of an UUID

    # Query the newly created Node to ensure everything is as expected
    query = """
        query {
            TestPerson {
                edges {
                    node {
                        id
                        name {
                            value
                            source {
                                id
                                display_label
                            }
                        }
                        height {
                            id
                            owner {
                                id
                                display_label
                            }
                        }
                    }
                }
            }
        }
    """
    gql_params = prepare_graphql_params(db=db, include_subscription=False, branch=default_branch)
    result1 = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert result1.errors is None
    assert result1.data["TestPerson"]["edges"][0]["node"]["name"]["source"]["id"] == first_account.id
    assert result1.data["TestPerson"]["edges"][0]["node"]["name"]["source"][
        "display_label"
    ] == await first_account.render_display_label(db=db)
    assert result1.data["TestPerson"]["edges"][0]["node"]["height"]["owner"]["id"] == second_account.id
    assert result1.data["TestPerson"]["edges"][0]["node"]["height"]["owner"][
        "display_label"
    ] == await second_account.render_display_label(db=db)


async def test_create_object_with_single_relationship(db: InfrahubDatabase, default_branch, car_person_schema):
    p1 = await Node.init(db=db, schema="TestPerson")
    await p1.new(db=db, name="John", height=180)
    await p1.save(db=db)

    query = """
    mutation {
        TestCarCreate(
            data: {
                name: { value: "Accord" }
                nbr_seats: { value: 5 }
                is_electric: { value: false }
                owner: { id: "John" }
            }
        ) {
            ok
            object {
                id
            }
        }
    }
    """
    gql_params = prepare_graphql_params(db=db, include_subscription=False, branch=default_branch)
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert result.data["TestCarCreate"]["ok"] is True
    assert len(result.data["TestCarCreate"]["object"]["id"]) == 36  # length of an UUID


async def test_create_object_with_single_relationship_flag_property(
    db: InfrahubDatabase, default_branch, car_person_schema
):
    p1 = await Node.init(db=db, schema="TestPerson")
    await p1.new(db=db, name="John", height=180)
    await p1.save(db=db)

    query = """
    mutation {
        TestCarCreate(data: {
            name: { value: "Accord" },
            nbr_seats: { value: 5 },
            is_electric: { value: false },
            owner: { id: "John", _relation__is_protected: true }
        }) {
            ok
            object {
                id
            }
        }
    }
    """
    gql_params = prepare_graphql_params(db=db, include_subscription=False, branch=default_branch)
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert result.data["TestCarCreate"]["ok"] is True
    assert len(result.data["TestCarCreate"]["object"]["id"]) == 36

    car = await NodeManager.get_one(db=db, id=result.data["TestCarCreate"]["object"]["id"])
    rm = await car.owner.get(db=db)
    assert rm.is_protected is True


async def test_create_object_with_single_relationship_node_property(
    db: InfrahubDatabase, default_branch, car_person_schema, first_account, second_account
):
    p1 = await Node.init(db=db, schema="TestPerson")
    await p1.new(db=db, name="John", height=180)
    await p1.save(db=db)

    query = (
        """
    mutation {
        TestCarCreate(
            data: {
                name: { value: "Accord" }
                nbr_seats: { value: 5 }
                is_electric: { value: false }
                owner: { id: "John", _relation__owner: "%s" }
            }
        ) {
            ok
            object {
                id
            }
        }
    }
    """
        % first_account.id
    )
    gql_params = prepare_graphql_params(db=db, include_subscription=False, branch=default_branch)
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert result.data["TestCarCreate"]["ok"] is True
    assert len(result.data["TestCarCreate"]["object"]["id"]) == 36

    car = await NodeManager.get_one(db=db, id=result.data["TestCarCreate"]["object"]["id"])
    rm = await car.owner.get(db=db)
    owner = await rm.get_owner(db=db)
    assert isinstance(owner, Node)
    assert owner.id == first_account.id


async def test_create_object_with_multiple_relationships(db: InfrahubDatabase, default_branch, fruit_tag_schema):
    t1 = await Node.init(db=db, schema=InfrahubKind.TAG)
    await t1.new(db=db, name="tag1")
    await t1.save(db=db)
    t2 = await Node.init(db=db, schema=InfrahubKind.TAG)
    await t2.new(db=db, name="tag2")
    await t2.save(db=db)
    t3 = await Node.init(db=db, schema=InfrahubKind.TAG)
    await t3.new(db=db, name="tag3")
    await t3.save(db=db)

    query = """
    mutation {
        GardenFruitCreate(
            data: {
                name: { value: "apple" }
                tags: [{ id: "tag1" }, { id: "tag2" }, { id: "tag3" }]
            }
        ) {
            ok
            object {
                id
            }
        }
    }
    """
    gql_params = prepare_graphql_params(db=db, include_subscription=False, branch=default_branch)
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert result.data["GardenFruitCreate"]["ok"] is True
    assert len(result.data["GardenFruitCreate"]["object"]["id"]) == 36  # length of an UUID

    fruit = await NodeManager.get_one(db=db, id=result.data["GardenFruitCreate"]["object"]["id"])
    assert len(await fruit.tags.get(db=db)) == 3


async def test_create_object_with_multiple_relationships_with_node_property(
    db: InfrahubDatabase, default_branch, fruit_tag_schema, first_account, second_account
):
    t1 = await Node.init(db=db, schema=InfrahubKind.TAG)
    await t1.new(db=db, name="tag1")
    await t1.save(db=db)
    t2 = await Node.init(db=db, schema=InfrahubKind.TAG)
    await t2.new(db=db, name="tag2")
    await t2.save(db=db)
    t3 = await Node.init(db=db, schema=InfrahubKind.TAG)
    await t3.new(db=db, name="tag3")
    await t3.save(db=db)

    query = """
    mutation {
        GardenFruitCreate(
            data: {
                name: { value: "apple" }
                tags: [
                    { id: "tag1", _relation__source: "%s" }
                    { id: "tag2", _relation__owner: "%s" }
                    { id: "tag3", _relation__source: "%s", _relation__owner: "%s" }
                ]
            }
        ) {
            ok
            object {
                id
            }
        }
    }
    """ % (
        first_account.id,
        second_account.id,
        first_account.id,
        second_account.id,
    )
    gql_params = prepare_graphql_params(db=db, include_subscription=False, branch=default_branch)
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert result.data["GardenFruitCreate"]["ok"] is True
    assert len(result.data["GardenFruitCreate"]["object"]["id"]) == 36  # length of an UUID

    fruit = await NodeManager.get_one(
        db=db, id=result.data["GardenFruitCreate"]["object"]["id"], include_owner=True, include_source=True
    )
    tags = {tag.peer_id: tag for tag in await fruit.tags.get(db=db)}
    assert len(tags) == 3

    t1_source = await tags[t1.id].get_source(db=db)
    t1_owner = await tags[t1.id].get_owner(db=db)
    t2_source = await tags[t2.id].get_source(db=db)
    t2_owner = await tags[t2.id].get_owner(db=db)
    t3_source = await tags[t3.id].get_source(db=db)
    t3_owner = await tags[t3.id].get_owner(db=db)

    assert isinstance(t1_source, Node)
    assert t1_source.id == first_account.id
    assert t1_owner is None
    assert t2_source is None
    assert isinstance(t2_owner, Node)
    assert t3_owner.id == second_account.id
    assert isinstance(t3_source, Node)
    assert t3_source.id == first_account.id
    assert isinstance(t3_owner, Node)
    assert t3_owner.id == second_account.id


async def test_create_object_with_multiple_relationships_flag_property(
    db: InfrahubDatabase, default_branch, fruit_tag_schema
):
    t1 = await Node.init(db=db, schema=InfrahubKind.TAG)
    await t1.new(db=db, name="tag1")
    await t1.save(db=db)
    t2 = await Node.init(db=db, schema=InfrahubKind.TAG)
    await t2.new(db=db, name="tag2")
    await t2.save(db=db)
    t3 = await Node.init(db=db, schema=InfrahubKind.TAG)
    await t3.new(db=db, name="tag3")
    await t3.save(db=db)

    query = """
    mutation {
        GardenFruitCreate(
            data: {
                name: { value: "apple" }
                tags: [
                    { id: "tag1", _relation__is_protected: true }
                    { id: "tag2", _relation__is_protected: true }
                    { id: "tag3", _relation__is_protected: true }
                ]
            }
        ) {
            ok
            object {
                id
            }
        }
    }
    """
    gql_params = prepare_graphql_params(db=db, include_subscription=False, branch=default_branch)
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert result.data["GardenFruitCreate"]["ok"] is True
    assert len(result.data["GardenFruitCreate"]["object"]["id"]) == 36  # length of an UUID

    fruit = await NodeManager.get_one(db=db, id=result.data["GardenFruitCreate"]["object"]["id"])
    rels = await fruit.tags.get(db=db)
    assert len(rels) == 3
    assert rels[0].is_protected is True
    assert rels[1].is_protected is True
    assert rels[2].is_protected is True


async def test_create_person_not_valid(db: InfrahubDatabase, default_branch, car_person_schema):
    query = """
    mutation {
        TestPersonCreate(data: {
            name: { value: "John"},
            height: {value: "182"}
        }) {
            ok
            object {
                id
            }
        }
    }
    """
    gql_params = prepare_graphql_params(db=db, include_subscription=False, branch=default_branch)
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert len(result.errors) == 1
    assert result.errors[0].message == "Expected value of type 'BigInt', found \"182\"."


async def test_create_with_attribute_not_valid(db: InfrahubDatabase, default_branch, car_person_schema):
    p1 = await Node.init(db=db, schema="TestPerson")
    await p1.new(db=db, name="John", height=180)
    await p1.save(db=db)

    query = """
    mutation {
        TestCarCreate(data: {
            name: { value: "Accord" },
            nbr_seats: { value: 5 },
            color: { value: "#44444444" },
            is_electric: { value: true },
            owner: { id: "John" },
        }) {
            ok
            object {
                id
            }
        }
    }
    """
    gql_params = prepare_graphql_params(db=db, include_subscription=False, branch=default_branch)
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert len(result.errors) == 1
    assert "#44444444 must have a maximum length of 7 at color" in result.errors[0].message


async def test_create_with_uniqueness_constraint_violation(db: InfrahubDatabase, default_branch, car_person_schema):
    car_schema = registry.schema.get("TestCar", branch=default_branch, duplicate=False)
    car_schema.uniqueness_constraints = [["owner", "color"]]

    p1 = await Node.init(db=db, schema="TestPerson")
    await p1.new(db=db, name="Bruce Wayne", height=180)
    await p1.save(db=db)
    c1 = await Node.init(db=db, schema="TestCar")
    await c1.new(db=db, name="Batmobile", is_electric=False, nbr_seats=3, color="#123456", owner=p1)
    await c1.save(db=db)

    query = """
    mutation {
        TestCarCreate(data: {
            name: { value: "Batcycle" },
            nbr_seats: { value: 1 },
            color: { value: "#123456" },
            is_electric: { value: true },
            owner: { id: "Bruce Wayne" },
        }) {
            ok
            object {
                id
            }
        }
    }
    """
    gql_params = prepare_graphql_params(db=db, include_subscription=False, branch=default_branch)
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )
    assert len(result.errors) == 1
    assert "Violates uniqueness constraint 'owner-color'" in result.errors[0].message


async def test_relationship_with_hfid(db: InfrahubDatabase, default_branch, animal_person_schema):
    person_schema = animal_person_schema.get(name="TestPerson")

    person1 = await Node.init(db=db, schema=person_schema, branch=default_branch)
    await person1.new(db=db, name="Jack")
    await person1.save(db=db)

    query = """
    mutation {
        TestDogCreate(data: {
            name: { value: "Rocky" },
            breed: { value: "Labrador" },
            color: { value: "black" },
            owner: { hfid: ["Jack"] },
        }) {
            ok
            object {
                id
            }
        }
    }
    """
    gql_params = prepare_graphql_params(db=db, include_subscription=False, branch=default_branch)
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )
    assert result.errors is None
    assert result.data["TestDogCreate"]["ok"] is True
    assert result.data["TestDogCreate"]["object"]["id"]


async def test_incorrect_peer_type_prevented(db: InfrahubDatabase, default_branch, animal_person_schema):
    person_schema = animal_person_schema.get(name="TestPerson")
    dog_schema = animal_person_schema.get(name="TestDog")

    person1 = await Node.init(db=db, schema=person_schema, branch=default_branch)
    await person1.new(db=db, name="Jack")
    await person1.save(db=db)

    person2 = await Node.init(db=db, schema=person_schema, branch=default_branch)
    await person2.new(db=db, name="Jill")
    await person2.save(db=db)

    dog1 = await Node.init(db=db, schema=dog_schema, branch=default_branch)
    await dog1.new(db=db, name="Rocky", breed="Labrador", owner=person1)
    await dog1.save(db=db)

    dog2 = await Node.init(db=db, schema=dog_schema, branch=default_branch)
    await dog2.new(db=db, name="Hank", breed="Chow", owner=person2)
    await dog2.save(db=db)

    query = """
    mutation {
        TestPersonCreate(data: {name: { value: "Herb"}, height: {value: 182}, animals: [{id: "%(animal_id)s"}]}) {
            ok
            object {
                id
            }
        }
    }
    """ % {"animal_id": person2.id}
    gql_params = prepare_graphql_params(db=db, include_subscription=False, branch=default_branch)
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )
    assert result.errors is not None
    assert len(result.errors) == 1
    assert (
        result.errors[0].message
        == f"""TestPerson - {person2.id} cannot be added to relationship, must be of type: ['TestCat', 'TestDog'] at animals"""
    )

    query = """
    mutation {
        TestDogCreate(data: {
            name: { value: "Rocky" },
            breed: { value: "Labrador" },
            color: { value: "black" },
            owner: { id: "%(owner_id)s" },
        }) {
            ok
            object {
                id
            }
        }
    }
    """ % {"owner_id": dog2.id}
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )
    assert result.errors is not None
    assert len(result.errors) == 1
    assert (
        result.errors[0].message
        == f"""TestDog - {dog2.id} cannot be added to relationship, must be of type: ['TestPerson'] at owner"""
    )


async def test_create_valid_datetime_success(db: InfrahubDatabase, default_branch, criticality_schema):
    query = """
    mutation {
        TestCriticalityCreate(data: {name: { value: "HIGH"}, level: {value: 1}, time: {value: "2021-01-01T00:00:00Z"}}) {
            ok
            object {
                id
            }
        }
    }
    """
    gql_params = prepare_graphql_params(db=db, include_subscription=False, branch=default_branch)
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )
    assert result.errors is None
    assert result.data["TestCriticalityCreate"]["ok"] is True
    crit = await NodeManager.get_one(db=db, id=result.data["TestCriticalityCreate"]["object"]["id"])
    assert crit.time.value == "2021-01-01T00:00:00Z"
    assert crit.time.is_default is False
    assert crit.name.value == "HIGH"
    assert crit.level.value == 1


async def test_create_valid_datetime_failure(db: InfrahubDatabase, default_branch, criticality_schema):
    query = """
    mutation {
        TestCriticalityCreate(data: {name: { value: "HIGH"}, level: {value: 1}, time: {value: "10:1010"}}) {
            ok
        }
    }
    """
    gql_params = prepare_graphql_params(db=db, include_subscription=False, branch=default_branch)
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )
    assert result.errors[0].args[0] == "10:1010 is not a valid DateTime at time"
    assert result.data["TestCriticalityCreate"] is None
