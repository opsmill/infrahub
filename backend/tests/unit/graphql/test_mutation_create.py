from graphql import graphql

from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.graphql import (
    generate_graphql_paginated_schema as generate_graphql_schema,
)


async def test_create_simple_object(db, session, default_branch, car_person_schema):
    query = """
    mutation {
        person_create(data: {name: { value: "John"}, height: {value: 182}}) {
            ok
            object {
                id
            }
        }
    }
    """
    result = await graphql(
        schema=await generate_graphql_schema(session=session, include_subscription=False, branch=default_branch),
        source=query,
        context_value={"infrahub_session": session, "infrahub_database": db, "infrahub_branch": default_branch},
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert result.data["person_create"]["ok"] is True
    assert len(result.data["person_create"]["object"]["id"]) == 36  # lenght of an UUID


async def test_create_check_unique(db, session, default_branch, car_person_schema):
    p1 = await Node.init(session=session, schema="Person")
    await p1.new(session=session, name="John", height=180)
    await p1.save(session=session)

    query = """
    mutation {
        person_create(data: {name: { value: "John"}, height: {value: 182}}) {
            ok
            object {
                id
            }
        }
    }
    """
    result = await graphql(
        schema=await generate_graphql_schema(session=session, include_subscription=False, branch=default_branch),
        source=query,
        context_value={"infrahub_session": session, "infrahub_database": db, "infrahub_branch": default_branch},
        root_value=None,
        variable_values={},
    )

    assert result.errors
    assert len(result.errors) == 1
    assert "An object already exist" in result.errors[0].message


async def test_all_attributes(db, session, default_branch, all_attribute_types_schema):
    query = """
    mutation {
        all_attribute_types_create(
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
        schema=await generate_graphql_schema(session=session, include_subscription=False, branch=default_branch),
        source=query,
        context_value={"infrahub_session": session, "infrahub_database": db, "infrahub_branch": default_branch},
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert result.data["all_attribute_types_create"]["ok"] is True
    assert len(result.data["all_attribute_types_create"]["object"]["id"]) == 36  # lenght of an UUID

    objs = await NodeManager.query(session=session, schema="AllAttributeTypes")
    obj1 = objs[0]

    assert obj1.mystring.value == "abc"
    assert obj1.mybool.value is False
    assert obj1.myint.value == 123
    assert obj1.mylist.value == ["1", 2, False]


async def test_create_object_with_flag_property(db, session, default_branch, car_person_schema):
    query = """
    mutation {
        person_create(
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
        schema=await generate_graphql_schema(session=session, include_subscription=False, branch=default_branch),
        source=query,
        context_value={"infrahub_session": session, "infrahub_database": db, "infrahub_branch": default_branch},
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert result.data["person_create"]["ok"] is True
    assert len(result.data["person_create"]["object"]["id"]) == 36  # lenght of an UUID

    # Query the newly created Node to ensure everything is as expected
    query = """
        query {
            person {
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
        schema=await generate_graphql_schema(session=session, include_subscription=False, branch=default_branch),
        source=query,
        context_value={"infrahub_session": session, "infrahub_database": db, "infrahub_branch": default_branch},
        root_value=None,
        variable_values={},
    )

    assert result1.errors is None
    assert result1.data["person"]["edges"][0]["node"]["name"]["is_protected"] is True
    assert result1.data["person"]["edges"][0]["node"]["height"]["is_visible"] is False


async def test_create_object_with_node_property(
    db, session, default_branch, car_person_schema, first_account, second_account
):
    graphql_schema = await generate_graphql_schema(session=session, include_subscription=False, branch=default_branch)

    query = """
    mutation {
        person_create(
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
        context_value={"infrahub_session": session, "infrahub_database": db, "infrahub_branch": default_branch},
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert result.data["person_create"]["ok"] is True
    assert len(result.data["person_create"]["object"]["id"]) == 36  # lenght of an UUID

    # Query the newly created Node to ensure everything is as expected
    query = """
        query {
            person {
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
        context_value={"infrahub_session": session, "infrahub_database": db, "infrahub_branch": default_branch},
        root_value=None,
        variable_values={},
    )

    assert result1.errors is None
    assert result1.data["person"]["edges"][0]["node"]["name"]["source"]["name"]["value"] == "First Account"
    assert result1.data["person"]["edges"][0]["node"]["height"]["owner"]["name"]["value"] == "Second Account"


async def test_create_object_with_single_relationship(db, session, default_branch, car_person_schema):
    p1 = await Node.init(session=session, schema="Person")
    await p1.new(session=session, name="John", height=180)
    await p1.save(session=session)

    query = """
    mutation {
        car_create(
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
        schema=await generate_graphql_schema(session=session, include_subscription=False, branch=default_branch),
        source=query,
        context_value={"infrahub_session": session, "infrahub_database": db, "infrahub_branch": default_branch},
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert result.data["car_create"]["ok"] is True
    assert len(result.data["car_create"]["object"]["id"]) == 36  # lenght of an UUID


async def test_create_object_with_single_relationship_flag_property(db, session, default_branch, car_person_schema):
    p1 = await Node.init(session=session, schema="Person")
    await p1.new(session=session, name="John", height=180)
    await p1.save(session=session)

    query = """
    mutation {
        car_create(data: {
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
        schema=await generate_graphql_schema(session=session, include_subscription=False, branch=default_branch),
        source=query,
        context_value={"infrahub_session": session, "infrahub_database": db, "infrahub_branch": default_branch},
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert result.data["car_create"]["ok"] is True
    assert len(result.data["car_create"]["object"]["id"]) == 36

    car = await NodeManager.get_one(session=session, id=result.data["car_create"]["object"]["id"])
    rm = await car.owner.get(session=session)
    assert rm.is_protected is True


async def test_create_object_with_single_relationship_node_property(
    db, session, default_branch, car_person_schema, first_account, second_account
):
    p1 = await Node.init(session=session, schema="Person")
    await p1.new(session=session, name="John", height=180)
    await p1.save(session=session)

    query = (
        """
    mutation {
        car_create(
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
        schema=await generate_graphql_schema(session=session, include_subscription=False, branch=default_branch),
        source=query,
        context_value={"infrahub_session": session, "infrahub_database": db, "infrahub_branch": default_branch},
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert result.data["car_create"]["ok"] is True
    assert len(result.data["car_create"]["object"]["id"]) == 36

    car = await NodeManager.get_one(session=session, id=result.data["car_create"]["object"]["id"])
    rm = await car.owner.get(session=session)
    owner = await rm.get_owner(session=session)
    assert isinstance(owner, Node)
    assert owner.id == first_account.id


async def test_create_object_with_multiple_relationships(db, session, default_branch, fruit_tag_schema):
    t1 = await Node.init(session=session, schema="Tag")
    await t1.new(session=session, name="tag1")
    await t1.save(session=session)
    t2 = await Node.init(session=session, schema="Tag")
    await t2.new(session=session, name="tag2")
    await t2.save(session=session)
    t3 = await Node.init(session=session, schema="Tag")
    await t3.new(session=session, name="tag3")
    await t3.save(session=session)

    query = """
    mutation {
        fruit_create(
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
        schema=await generate_graphql_schema(session=session, include_subscription=False, branch=default_branch),
        source=query,
        context_value={"infrahub_session": session, "infrahub_database": db, "infrahub_branch": default_branch},
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert result.data["fruit_create"]["ok"] is True
    assert len(result.data["fruit_create"]["object"]["id"]) == 36  # lenght of an UUID

    fruit = await NodeManager.get_one(session=session, id=result.data["fruit_create"]["object"]["id"])
    assert len(await fruit.tags.get(session=session)) == 3


async def test_create_object_with_multiple_relationships_with_node_property(
    db, session, default_branch, fruit_tag_schema, first_account, second_account
):
    t1 = await Node.init(session=session, schema="Tag")
    await t1.new(session=session, name="tag1")
    await t1.save(session=session)
    t2 = await Node.init(session=session, schema="Tag")
    await t2.new(session=session, name="tag2")
    await t2.save(session=session)
    t3 = await Node.init(session=session, schema="Tag")
    await t3.new(session=session, name="tag3")
    await t3.save(session=session)

    query = """
    mutation {
        fruit_create(
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
        schema=await generate_graphql_schema(session=session, include_subscription=False, branch=default_branch),
        source=query,
        context_value={"infrahub_session": session, "infrahub_database": db, "infrahub_branch": default_branch},
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert result.data["fruit_create"]["ok"] is True
    assert len(result.data["fruit_create"]["object"]["id"]) == 36  # lenght of an UUID

    fruit = await NodeManager.get_one(
        session=session, id=result.data["fruit_create"]["object"]["id"], include_owner=True, include_source=True
    )
    tags = {tag.peer_id: tag for tag in await fruit.tags.get(session=session)}
    assert len(tags) == 3

    t1_source = await tags[t1.id].get_source(session=session)
    t1_owner = await tags[t1.id].get_owner(session=session)
    t2_source = await tags[t2.id].get_source(session=session)
    t2_owner = await tags[t2.id].get_owner(session=session)
    t3_source = await tags[t3.id].get_source(session=session)
    t3_owner = await tags[t3.id].get_owner(session=session)

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


async def test_create_object_with_multiple_relationships_flag_property(db, session, default_branch, fruit_tag_schema):
    t1 = await Node.init(session=session, schema="Tag")
    await t1.new(session=session, name="tag1")
    await t1.save(session=session)
    t2 = await Node.init(session=session, schema="Tag")
    await t2.new(session=session, name="tag2")
    await t2.save(session=session)
    t3 = await Node.init(session=session, schema="Tag")
    await t3.new(session=session, name="tag3")
    await t3.save(session=session)

    query = """
    mutation {
        fruit_create(
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
        schema=await generate_graphql_schema(session=session, include_subscription=False, branch=default_branch),
        source=query,
        context_value={"infrahub_session": session, "infrahub_database": db, "infrahub_branch": default_branch},
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert result.data["fruit_create"]["ok"] is True
    assert len(result.data["fruit_create"]["object"]["id"]) == 36  # lenght of an UUID

    fruit = await NodeManager.get_one(session=session, id=result.data["fruit_create"]["object"]["id"])
    rels = await fruit.tags.get(session=session)
    assert len(rels) == 3
    assert rels[0].is_protected is True
    assert rels[1].is_protected is True
    assert rels[2].is_protected is True


async def test_create_person_not_valid(db, session, default_branch, car_person_schema):
    query = """
    mutation {
        person_create(data: {
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
        schema=await generate_graphql_schema(session=session, include_subscription=False, branch=default_branch),
        source=query,
        context_value={"infrahub_session": session, "infrahub_database": db, "infrahub_branch": default_branch},
        root_value=None,
        variable_values={},
    )

    assert len(result.errors) == 1
    assert "Int cannot represent non-integer value" in result.errors[0].message


async def test_create_with_attribute_not_valid(db, session, default_branch, car_person_schema):
    p1 = await Node.init(session=session, schema="Person")
    await p1.new(session=session, name="John", height=180)
    await p1.save(session=session)

    query = """
    mutation {
        car_create(data: {
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
        schema=await generate_graphql_schema(session=session, include_subscription=False, branch=default_branch),
        source=query,
        context_value={"infrahub_session": session, "infrahub_database": db, "infrahub_branch": default_branch},
        root_value=None,
        variable_values={},
    )

    assert len(result.errors) == 1
    assert "#44444444 must have a maximum length of 7 at color" in result.errors[0].message
