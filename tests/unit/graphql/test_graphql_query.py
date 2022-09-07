import graphene
import pytest
from graphql import graphql

from infrahub.core import registry
from infrahub.core.node import Node
from infrahub.core.timestamp import Timestamp
from infrahub.graphql import get_gql_mutation, get_gql_query


@pytest.mark.asyncio
async def test_simple_query(default_branch, criticality_schema):

    Node(criticality_schema).new(name="low", level=4).save()
    Node(criticality_schema).new(name="medium", level=3, description="My desc", color="#333333").save()

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
        graphene.Schema(query=get_gql_query(), auto_camelcase=False).graphql_schema,
        source=query,
        context_value={},
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert len(result.data["criticality"]) == 2


@pytest.mark.asyncio
async def test_nested_query(default_branch, car_person_schema):

    car = registry.get_schema("Car")
    person = registry.get_schema("Person")

    p1 = Node(person).new(name="John", height=180).save()
    p2 = Node(person).new(name="Jane", height=170).save()

    Node(car).new(name="volt", nbr_seats=4, is_electric=True, owner=p1).save()
    Node(car).new(name="bolt", nbr_seats=4, is_electric=True, owner=p1).save()
    Node(car).new(name="nolt", nbr_seats=4, is_electric=True, owner=p2).save()

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
        graphene.Schema(query=get_gql_query(), auto_camelcase=False).graphql_schema,
        source=query,
        context_value={},
        root_value=None,
        variable_values={},
    )

    assert result.errors is None

    result_per_name = {result["name"]["value"]: result for result in result.data["person"]}
    assert sorted(result_per_name.keys()) == ["Jane", "John"]
    assert len(result_per_name["John"]["cars"]) == 2
    assert len(result_per_name["Jane"]["cars"]) == 1


@pytest.mark.asyncio
async def test_query_filter_local_attrs(default_branch, criticality_schema):

    Node(criticality_schema).new(name="low", level=4).save()
    Node(criticality_schema).new(name="medium", level=3, description="My desc", color="#333333").save()

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
        graphene.Schema(query=get_gql_query(), auto_camelcase=False).graphql_schema,
        source=query,
        context_value={},
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert len(result.data["criticality"]) == 1


@pytest.mark.asyncio
async def test_query_filter_relationships(default_branch, car_person_schema):

    car = registry.get_schema("Car")
    person = registry.get_schema("Person")

    p1 = Node(person).new(name="John", height=180).save()
    p2 = Node(person).new(name="Jane", height=170).save()

    Node(car).new(name="volt", nbr_seats=4, is_electric=True, owner=p1).save()
    Node(car).new(name="bolt", nbr_seats=4, is_electric=True, owner=p1).save()
    Node(car).new(name="nolt", nbr_seats=4, is_electric=True, owner=p2).save()

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
        graphene.Schema(query=get_gql_query(), auto_camelcase=False).graphql_schema,
        source=query,
        context_value={},
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert len(result.data["person"]) == 1
    assert result.data["person"][0]["name"]["value"] == "John"
    assert len(result.data["person"][0]["cars"]) == 1
    assert result.data["person"][0]["cars"][0]["name"]["value"] == "volt"


@pytest.mark.asyncio
async def test_query_oneway_relationship(default_branch, person_tag_schema):

    t1 = Node("Tag").new(name="Blue", description="The Blue tag").save()
    t2 = Node("Tag").new(name="Red").save()
    Node("Person").new(firstname="John", lastname="Doe", tags=[t1, t2]).save()

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
        graphene.Schema(query=get_gql_query(), mutation=get_gql_mutation(), auto_camelcase=False).graphql_schema,
        source=query,
        context_value={},
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert len(result.data["person"][0]["tags"]) == 2


@pytest.mark.asyncio
async def test_query_at_specific_time(default_branch, person_tag_schema):

    Node("Tag").new(name="Blue", description="The Blue tag").save()
    t2 = Node("Tag").new(name="Red").save()

    time1 = Timestamp()

    t2.name.value = "Green"
    t2.save()

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
        graphene.Schema(query=get_gql_query(), mutation=get_gql_mutation(), auto_camelcase=False).graphql_schema,
        source=query,
        context_value={},
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
        graphene.Schema(query=get_gql_query(), mutation=get_gql_mutation(), auto_camelcase=False).graphql_schema,
        source=query,
        context_value={"infrahub_at": time1},
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert len(result.data["tag"]) == 2
    names = sorted([tag["name"]["value"] for tag in result.data["tag"]])
    assert names == ["Blue", "Red"]
