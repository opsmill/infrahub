import graphene
import pytest
from graphql import graphql

from infrahub.core import registry
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.timestamp import Timestamp
from infrahub.graphql import get_gql_query


@pytest.mark.asyncio
async def test_simple_query(db, session, default_branch, criticality_schema):

    obj1 = await Node.init(session=session, schema=criticality_schema)
    await obj1.new(session=session, name="low", level=4)
    await obj1.save(session=session)
    obj2 = await Node.init(session=session, schema=criticality_schema)
    await obj2.new(session=session, name="medium", level=3, description="My desc", color="#333333")
    await obj2.save(session=session)

    query = """
    query {
        criticality {
            name {
                value
            }
        }
    }
    """
    result = await graphql(
        graphene.Schema(query=await get_gql_query(session=session), auto_camelcase=False).graphql_schema,
        source=query,
        context_value={"infrahub_session": session, "infrahub_database": db},
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert len(result.data["criticality"]) == 2


@pytest.mark.asyncio
async def test_nested_query(db, session, default_branch, car_person_schema):

    car = await registry.get_schema(session=session, name="Car")
    person = await registry.get_schema(session=session, name="Person")

    p1 = await Node.init(session=session, schema=person)
    await p1.new(session=session, name="John", height=180)
    await p1.save(session=session)
    p2 = await Node.init(session=session, schema=person)
    await p2.new(session=session, name="Jane", height=170)
    await p2.save(session=session)

    c1 = await Node.init(session=session, schema=car)
    await c1.new(session=session, name="volt", nbr_seats=4, is_electric=True, owner=p1)
    await c1.save(session=session)
    c2 = await Node.init(session=session, schema=car)
    await c2.new(session=session, name="bolt", nbr_seats=4, is_electric=True, owner=p1)
    await c2.save(session=session)
    c3 = await Node.init(session=session, schema=car)
    await c3.new(session=session, name="nolt", nbr_seats=4, is_electric=True, owner=p2)
    await c3.save(session=session)

    query = """
    query {
        person {
            name {
                value
            }
            cars {
                name {
                    value
                }
            }
        }
    }
    """
    result = await graphql(
        graphene.Schema(query=await get_gql_query(session=session), auto_camelcase=False).graphql_schema,
        source=query,
        context_value={"infrahub_session": session, "infrahub_database": db},
        root_value=None,
        variable_values={},
    )

    assert result.errors is None

    result_per_name = {result["name"]["value"]: result for result in result.data["person"]}
    assert sorted(result_per_name.keys()) == ["Jane", "John"]
    assert len(result_per_name["John"]["cars"]) == 2
    assert len(result_per_name["Jane"]["cars"]) == 1


@pytest.mark.asyncio
async def test_query_filter_local_attrs(db, session, default_branch, criticality_schema):

    obj1 = await Node.init(session=session, schema=criticality_schema)
    await obj1.new(session=session, name="low", level=4)
    await obj1.save(session=session)
    obj2 = await Node.init(session=session, schema=criticality_schema)
    await obj2.new(session=session, name="medium", level=3, description="My desc", color="#333333")
    await obj2.save(session=session)

    query = """
    query {
        criticality(name__value: "low") {
            name {
                value
            }
        }
    }
    """
    result = await graphql(
        graphene.Schema(query=await get_gql_query(session=session), auto_camelcase=False).graphql_schema,
        source=query,
        context_value={"infrahub_session": session, "infrahub_database": db},
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert len(result.data["criticality"]) == 1


@pytest.mark.asyncio
async def test_query_filter_relationships(db, session, default_branch, car_person_schema):

    car = await registry.get_schema(session=session, name="Car")
    person = await registry.get_schema(session=session, name="Person")

    p1 = await Node.init(session=session, schema=person)
    await p1.new(session=session, name="John", height=180)
    await p1.save(session=session)
    p2 = await Node.init(session=session, schema=person)
    await p2.new(session=session, name="Jane", height=170)
    await p2.save(session=session)

    c1 = await Node.init(session=session, schema=car)
    await c1.new(session=session, name="volt", nbr_seats=4, is_electric=True, owner=p1)
    await c1.save(session=session)
    c2 = await Node.init(session=session, schema=car)
    await c2.new(session=session, name="bolt", nbr_seats=4, is_electric=True, owner=p1)
    await c2.save(session=session)
    c3 = await Node.init(session=session, schema=car)
    await c3.new(session=session, name="nolt", nbr_seats=4, is_electric=True, owner=p2)
    await c3.save(session=session)

    query = """
    query {
        person(name__value: "John") {
            name {
                value
            }
            cars(name__value: "volt") {
                name {
                    value
                }
            }
        }
    }
    """
    result = await graphql(
        graphene.Schema(query=await get_gql_query(session=session), auto_camelcase=False).graphql_schema,
        source=query,
        context_value={"infrahub_session": session, "infrahub_database": db},
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert len(result.data["person"]) == 1
    assert result.data["person"][0]["name"]["value"] == "John"
    assert len(result.data["person"][0]["cars"]) == 1
    assert result.data["person"][0]["cars"][0]["name"]["value"] == "volt"


@pytest.mark.asyncio
async def test_query_oneway_relationship(db, session, default_branch, person_tag_schema):

    t1 = await Node.init(session=session, schema="Tag")
    await t1.new(session=session, name="Blue", description="The Blue tag")
    await t1.save(session=session)
    t2 = await Node.init(session=session, schema="Tag")
    await t2.new(session=session, name="Red")
    await t2.save(session=session)
    p1 = await Node.init(session=session, schema="Person")
    await p1.new(session=session, firstname="John", lastname="Doe", tags=[t1, t2])
    await p1.save(session=session)

    query = """
    query {
        person {
            id
            tags {
                name {
                    value
                }
            }
        }
    }
    """
    result = await graphql(
        graphene.Schema(query=await get_gql_query(session=session), auto_camelcase=False).graphql_schema,
        source=query,
        context_value={"infrahub_session": session, "infrahub_database": db},
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert len(result.data["person"][0]["tags"]) == 2


@pytest.mark.asyncio
async def test_query_at_specific_time(db, session, default_branch, person_tag_schema):

    t1 = await Node.init(session=session, schema="Tag")
    await t1.new(session=session, name="Blue", description="The Blue tag")
    await t1.save(session=session)
    t2 = await Node.init(session=session, schema="Tag")
    await t2.new(session=session, name="Red")
    await t2.save(session=session)

    time1 = Timestamp()

    t2.name.value = "Green"
    await t2.save(session=session)

    query = """
    query {
        tag {
            name {
                value
            }
        }
    }
    """
    result = await graphql(
        graphene.Schema(query=await get_gql_query(session=session), auto_camelcase=False).graphql_schema,
        source=query,
        context_value={"infrahub_session": session, "infrahub_database": db},
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert len(result.data["tag"]) == 2
    names = sorted([tag["name"]["value"] for tag in result.data["tag"]])
    assert names == ["Blue", "Green"]

    # Now query at a specific time
    query = """
    query {
        tag {
            name {
                value
            }
        }
    }
    """

    result = await graphql(
        graphene.Schema(query=await get_gql_query(session=session), auto_camelcase=False).graphql_schema,
        source=query,
        context_value={"infrahub_session": session, "infrahub_database": db, "infrahub_at": time1},
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert len(result.data["tag"]) == 2
    names = sorted([tag["name"]["value"] for tag in result.data["tag"]])
    assert names == ["Blue", "Red"]


@pytest.mark.asyncio
async def test_query_attribute_updated_at(db, session, default_branch, person_tag_schema):

    p11 = await Node.init(session=session, schema="Person")
    await p11.new(session=session, firstname="John", lastname="Doe")
    await p11.save(session=session)

    query = """
    query {
        person {
            id
            firstname {
                value
                updated_at
            }
            lastname {
                value
                updated_at
            }
        }
    }
    """
    result1 = await graphql(
        graphene.Schema(query=await get_gql_query(session=session), auto_camelcase=False).graphql_schema,
        source=query,
        context_value={"infrahub_session": session, "infrahub_database": db},
        root_value=None,
        variable_values={},
    )

    assert result1.errors is None
    assert result1.data["person"][0]["firstname"]["updated_at"]
    assert result1.data["person"][0]["firstname"]["updated_at"] == result1.data["person"][0]["lastname"]["updated_at"]

    p12 = await NodeManager.get_one(session=session, id=p11.id)
    p12.firstname.value = "Jim"
    await p12.save(session=session)

    result2 = await graphql(
        graphene.Schema(query=await get_gql_query(session=session), auto_camelcase=False).graphql_schema,
        source=query,
        context_value={"infrahub_session": session, "infrahub_database": db},
        root_value=None,
        variable_values={},
    )

    assert result2.errors is None
    assert result2.data["person"][0]["firstname"]["updated_at"]
    assert result2.data["person"][0]["firstname"]["updated_at"] != result2.data["person"][0]["lastname"]["updated_at"]


@pytest.mark.asyncio
async def test_query_node_updated_at(db, session, default_branch, person_tag_schema):

    p1 = await Node.init(session=session, schema="Person")
    await p1.new(session=session, firstname="John", lastname="Doe")
    await p1.save(session=session)

    query = """
    query {
        person {
            _updated_at
            id
        }
    }
    """
    result1 = await graphql(
        graphene.Schema(query=await get_gql_query(session=session), auto_camelcase=False).graphql_schema,
        source=query,
        context_value={"infrahub_session": session, "infrahub_database": db},
        root_value=None,
        variable_values={},
    )

    assert result1.errors is None
    assert result1.data["person"][0]["_updated_at"]

    p2 = await Node.init(session=session, schema="Person")
    await p2.new(session=session, firstname="Jane", lastname="Doe")
    await p2.save(session=session)

    result2 = await graphql(
        graphene.Schema(query=await get_gql_query(session=session), auto_camelcase=False).graphql_schema,
        source=query,
        context_value={"infrahub_session": session, "infrahub_database": db},
        root_value=None,
        variable_values={},
    )

    assert result2.errors is None
    assert result2.data["person"][0]["_updated_at"]
    assert result2.data["person"][1]["_updated_at"]
    assert result2.data["person"][1]["_updated_at"] == Timestamp(result2.data["person"][1]["_updated_at"]).to_string()
    assert result2.data["person"][0]["_updated_at"] != result2.data["person"][1]["_updated_at"]


@pytest.mark.asyncio
async def test_query_relationship_updated_at(db, session, default_branch, person_tag_schema):

    t1 = await Node.init(session=session, schema="Tag")
    await t1.new(session=session, name="Blue", description="The Blue tag")
    await t1.save(session=session)
    t2 = await Node.init(session=session, schema="Tag")
    await t2.new(session=session, name="Red")
    await t2.save(session=session)

    query = """
    query {
        person {
            id
            tags {
                _updated_at
                _relation__updated_at
                name {
                    value
                }
            }
        }
    }
    """
    result1 = await graphql(
        graphene.Schema(query=await get_gql_query(session=session), auto_camelcase=False).graphql_schema,
        source=query,
        context_value={"infrahub_session": session, "infrahub_database": db},
        root_value=None,
        variable_values={},
    )

    assert result1.errors is None
    assert result1.data["person"] == []

    p1 = await Node.init(session=session, schema="Person")
    await p1.new(session=session, firstname="John", lastname="Doe", tags=[t1, t2])
    await p1.save(session=session)

    result2 = await graphql(
        graphene.Schema(query=await get_gql_query(session=session), auto_camelcase=False).graphql_schema,
        source=query,
        context_value={"infrahub_session": session, "infrahub_database": db},
        root_value=None,
        variable_values={},
    )

    assert result2.errors is None
    assert len(result2.data["person"][0]["tags"]) == 2
    assert (
        result2.data["person"][0]["tags"][0]["_updated_at"]
        != result2.data["person"][0]["tags"][0]["_relation__updated_at"]
    )
    assert (
        result2.data["person"][0]["tags"][0]["_updated_at"]
        == Timestamp(result2.data["person"][0]["tags"][0]["_updated_at"]).to_string()
    )


@pytest.mark.asyncio
async def test_query_attribute_source(
    db, session, default_branch, register_core_models_schema, person_tag_schema, first_account
):

    p1 = await Node.init(session=session, schema="Person")
    await p1.new(session=session, firstname="John", lastname="Doe", _source=first_account)
    await p1.save(session=session)

    query = """
    query {
        person {
            id
            firstname {
                value
                source {
                    name {
                        value
                    }
                }
            }
        }
    }
    """
    result1 = await graphql(
        graphene.Schema(query=await get_gql_query(session=session), auto_camelcase=False).graphql_schema,
        source=query,
        context_value={"infrahub_session": session, "infrahub_database": db},
        root_value=None,
        variable_values={},
    )

    assert result1.errors is None
    assert result1.data["person"][0]["firstname"]["source"]
    assert result1.data["person"][0]["firstname"]["source"]["name"]["value"] == first_account.name.value


@pytest.mark.asyncio
async def test_query_attribute_source2(
    db, session, default_branch, register_core_models_schema, person_tag_schema, first_account
):

    p1 = await Node.init(session=session, schema="Person")
    await p1.new(
        session=session,
        firstname={"value": "John", "is_protected": True},
        lastname={"value": "Doe", "is_visible": False},
        _source=first_account,
    )
    await p1.save(session=session)

    query = """
    query {
        person {
            id
            firstname {
                value
                is_protected
            }
            lastname {
                value
                is_visible
            }
        }
    }
    """
    result1 = await graphql(
        graphene.Schema(query=await get_gql_query(session=session), auto_camelcase=False).graphql_schema,
        source=query,
        context_value={"infrahub_session": session, "infrahub_database": db},
        root_value=None,
        variable_values={},
    )

    assert result1.errors is None
    assert result1.data["person"][0]["firstname"]["is_protected"] is True
    assert result1.data["person"][0]["lastname"]["is_visible"] is False
