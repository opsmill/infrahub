import pytest
from graphql import graphql

from infrahub.core.constants import InfrahubKind
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.database import InfrahubDatabase
from infrahub.graphql import generate_graphql_schema


@pytest.fixture(autouse=True)
def load_graphql_requirements(group_graphql):
    pass


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
    result = await graphql(
        schema=await generate_graphql_schema(db=db, include_subscription=False, branch=default_branch),
        source=query,
        context_value={"infrahub_database": db, "infrahub_branch": default_branch, "related_node_ids": set()},
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert result.data["TestPersonCreate"]["ok"] is True
    assert len(result.data["TestPersonCreate"]["object"]["id"]) == 36  # lenght of an UUID


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
    result = await graphql(
        schema=await generate_graphql_schema(db=db, include_subscription=False, branch=default_branch),
        source=query,
        context_value={"infrahub_database": db, "infrahub_branch": default_branch, "related_node_ids": set()},
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
    result = await graphql(
        schema=await generate_graphql_schema(db=db, include_subscription=False, branch=default_branch),
        source=query,
        context_value={"infrahub_database": db, "infrahub_branch": default_branch, "related_node_ids": set()},
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
    result = await graphql(
        schema=await generate_graphql_schema(db=db, include_subscription=False, branch=default_branch),
        source=query,
        context_value={"infrahub_database": db, "infrahub_branch": default_branch, "related_node_ids": set()},
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

    result = await graphql(
        schema=await generate_graphql_schema(db=db, include_subscription=False, branch=branch1),
        source=query,
        context_value={"infrahub_database": db, "infrahub_branch": branch1},
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
    result = await graphql(
        schema=await generate_graphql_schema(db=db, include_subscription=False, branch=branch1),
        source=query,
        context_value={"infrahub_database": db, "infrahub_branch": branch1},
        root_value=None,
        variable_values={},
    )

    assert result.errors
    assert len(result.errors) == 1
    assert "An object already exist" in result.errors[0].message


async def test_create_check_unique_in_generic(db: InfrahubDatabase, default_branch, car_person_schema_with_generic):
    p1 = await Node.init(db=db, schema="TestPerson")
    await p1.new(db=db, name="John", height=180)
    await p1.save(db=db)

    query = """
    mutation {
        TestCylonCreate(data: {name: { value: "John"}, height: {value: 182}, model_number: { value: 6 }}) {
            ok
            object {
                id
            }
        }
    }
    """
    result = await graphql(
        schema=await generate_graphql_schema(db=db, include_subscription=False, branch=default_branch),
        source=query,
        context_value={"infrahub_database": db, "infrahub_branch": default_branch},
        root_value=None,
        variable_values={},
    )

    assert result.errors
    assert len(result.errors) == 1
    assert "An object already exist" in result.errors[0].message


async def test_create_check_uniques_allowed_within_generic(db: InfrahubDatabase, default_branch, car_person_schema):
    p1 = await Node.init(db=db, schema="TestPerson")
    await p1.new(db=db, name="John", height=180)
    await p1.save(db=db)

    gql_schema = await generate_graphql_schema(db=db, include_subscription=False, branch=default_branch)
    mutation = """
    mutation {
        TestCylonCreate(data: {name: { value: "John"}, height: {value: 182}, model_number: { value: 6 }}) {
            ok
            object {
                id
                name { value }
            }
        }
    }
    """
    result = await graphql(
        schema=gql_schema,
        source=mutation,
        context_value={"infrahub_database": db, "infrahub_branch": default_branch},
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert result.data["TestCylonCreate"]["ok"] is True
    assert result.data["TestCylonCreate"]["object"]["name"]["value"] == "John"


async def test_create_check_uniques_allowed_within_overridden_generic(
    db: InfrahubDatabase, default_branch, car_person_schema_generic_with_unique_override
):
    p1 = await Node.init(db=db, schema="TestPerson")
    await p1.new(db=db, name="John", height=180)
    await p1.save(db=db)

    gql_schema = await generate_graphql_schema(db=db, include_subscription=False, branch=default_branch)
    mutation = """
    mutation {
        TestCylonCreate(data: {name: { value: "John"}, height: {value: 182}, model_number: { value: 6 }}) {
            ok
            object {
                id
                name { value }
            }
        }
    }
    """
    result = await graphql(
        schema=gql_schema,
        source=mutation,
        context_value={"infrahub_database": db, "infrahub_branch": default_branch},
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert result.data["TestCylonCreate"]["ok"] is True
    assert result.data["TestCylonCreate"]["object"]["name"]["value"] == "John"


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
            }
        ){
            ok
            object {
                id
            }
        }
    }
    """

    result = await graphql(
        schema=await generate_graphql_schema(db=db, include_subscription=False, branch=default_branch),
        source=query,
        context_value={"infrahub_database": db, "infrahub_branch": default_branch, "related_node_ids": set()},
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert result.data["TestAllAttributeTypesCreate"]["ok"] is True
    assert len(result.data["TestAllAttributeTypesCreate"]["object"]["id"]) == 36  # lenght of an UUID

    objs = await NodeManager.query(db=db, schema="TestAllAttributeTypes")
    obj1 = objs[0]

    assert obj1.mystring.value == "abc"
    assert obj1.mybool.value is False
    assert obj1.myint.value == 123
    assert obj1.mylist.value == ["1", 2, False]


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
    result = await graphql(
        schema=await generate_graphql_schema(db=db, include_subscription=False, branch=default_branch),
        source=query,
        context_value={"infrahub_database": db, "infrahub_branch": default_branch, "related_node_ids": set()},
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert result.data["TestPersonCreate"]["ok"] is True
    assert len(result.data["TestPersonCreate"]["object"]["id"]) == 36  # lenght of an UUID

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
    result1 = await graphql(
        schema=await generate_graphql_schema(db=db, include_subscription=False, branch=default_branch),
        source=query,
        context_value={"infrahub_database": db, "infrahub_branch": default_branch, "related_node_ids": set()},
        root_value=None,
        variable_values={},
    )

    assert result1.errors is None
    assert result1.data["TestPerson"]["edges"][0]["node"]["name"]["is_protected"] is True
    assert result1.data["TestPerson"]["edges"][0]["node"]["height"]["is_visible"] is False


async def test_create_object_with_node_property(
    db: InfrahubDatabase, default_branch, car_person_schema, first_account, second_account
):
    graphql_schema = await generate_graphql_schema(db=db, include_subscription=False, branch=default_branch)

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

    result = await graphql(
        graphql_schema,
        source=query,
        context_value={"infrahub_database": db, "infrahub_branch": default_branch, "related_node_ids": set()},
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert result.data["TestPersonCreate"]["ok"] is True
    assert len(result.data["TestPersonCreate"]["object"]["id"]) == 36  # lenght of an UUID

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
                                name {
                                    value
                                }
                            }
                        }
                        height {
                            id
                            owner {
                                name {
                                    value
                                }
                            }
                        }
                    }
                }
            }
        }
    """
    result1 = await graphql(
        graphql_schema,
        source=query,
        context_value={"infrahub_database": db, "infrahub_branch": default_branch, "related_node_ids": set()},
        root_value=None,
        variable_values={},
    )

    assert result1.errors is None
    assert result1.data["TestPerson"]["edges"][0]["node"]["name"]["source"]["name"]["value"] == "First Account"
    assert result1.data["TestPerson"]["edges"][0]["node"]["height"]["owner"]["name"]["value"] == "Second Account"


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

    result = await graphql(
        schema=await generate_graphql_schema(db=db, include_subscription=False, branch=default_branch),
        source=query,
        context_value={"infrahub_database": db, "infrahub_branch": default_branch, "related_node_ids": set()},
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert result.data["TestCarCreate"]["ok"] is True
    assert len(result.data["TestCarCreate"]["object"]["id"]) == 36  # lenght of an UUID


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

    result = await graphql(
        schema=await generate_graphql_schema(db=db, include_subscription=False, branch=default_branch),
        source=query,
        context_value={"infrahub_database": db, "infrahub_branch": default_branch, "related_node_ids": set()},
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

    result = await graphql(
        schema=await generate_graphql_schema(db=db, include_subscription=False, branch=default_branch),
        source=query,
        context_value={"infrahub_database": db, "infrahub_branch": default_branch, "related_node_ids": set()},
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

    result = await graphql(
        schema=await generate_graphql_schema(db=db, include_subscription=False, branch=default_branch),
        source=query,
        context_value={"infrahub_database": db, "infrahub_branch": default_branch, "related_node_ids": set()},
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert result.data["GardenFruitCreate"]["ok"] is True
    assert len(result.data["GardenFruitCreate"]["object"]["id"]) == 36  # lenght of an UUID

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

    result = await graphql(
        schema=await generate_graphql_schema(db=db, include_subscription=False, branch=default_branch),
        source=query,
        context_value={"infrahub_database": db, "infrahub_branch": default_branch, "related_node_ids": set()},
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert result.data["GardenFruitCreate"]["ok"] is True
    assert len(result.data["GardenFruitCreate"]["object"]["id"]) == 36  # lenght of an UUID

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

    result = await graphql(
        schema=await generate_graphql_schema(db=db, include_subscription=False, branch=default_branch),
        source=query,
        context_value={"infrahub_database": db, "infrahub_branch": default_branch, "related_node_ids": set()},
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert result.data["GardenFruitCreate"]["ok"] is True
    assert len(result.data["GardenFruitCreate"]["object"]["id"]) == 36  # lenght of an UUID

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
    result = await graphql(
        schema=await generate_graphql_schema(db=db, include_subscription=False, branch=default_branch),
        source=query,
        context_value={"infrahub_database": db, "infrahub_branch": default_branch, "related_node_ids": set()},
        root_value=None,
        variable_values={},
    )

    assert len(result.errors) == 1
    assert "Int cannot represent non-integer value" in result.errors[0].message


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
    result = await graphql(
        schema=await generate_graphql_schema(db=db, include_subscription=False, branch=default_branch),
        source=query,
        context_value={"infrahub_database": db, "infrahub_branch": default_branch, "related_node_ids": set()},
        root_value=None,
        variable_values={},
    )

    assert len(result.errors) == 1
    assert "#44444444 must have a maximum length of 7 at color" in result.errors[0].message
