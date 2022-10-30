import graphene
import pytest
from graphql import graphql
from infrahub.core.manager import NodeManager

from infrahub.core.node import Node
from infrahub.graphql import get_gql_mutation, get_gql_query


@pytest.mark.asyncio
async def test_create_simple_object(default_branch, car_person_schema):

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
        graphene.Schema(query=get_gql_query(), mutation=get_gql_mutation(), auto_camelcase=False).graphql_schema,
        source=query,
        context_value={},
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert result.data["person_create"]["ok"] is True
    assert len(result.data["person_create"]["object"]["id"]) == 36  # lenght of an UUID


@pytest.mark.asyncio
async def test_create_object_with_flag_property(default_branch, car_person_schema):

    graphql_schema = graphene.Schema(
        query=get_gql_query(), mutation=get_gql_mutation(), auto_camelcase=False
    ).graphql_schema

    query = """
    mutation {
        person_create(data: {name: { value: "John", is_protected: true}, height: {value: 182, is_visible: false}}) {
            ok
            object {
                id
            }
        }
    }
    """
    result = await graphql(
        graphql_schema,
        source=query,
        context_value={},
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
    """
    result1 = await graphql(
        graphql_schema,
        source=query,
        context_value={},
        root_value=None,
        variable_values={},
    )

    assert result1.errors is None
    assert result1.data["person"][0]["name"]["is_protected"] == True
    assert result1.data["person"][0]["height"]["is_visible"] == False


@pytest.mark.asyncio
async def test_create_object_with_single_relationship(default_branch, car_person_schema):

    Node("Person").new(name="John", height=180).save()

    query = """
    mutation {
        car_create(data: {
            name: { value: "Accord" },
            nbr_seats: { value: 5 },
            is_electric: { value: false },
            owner: { id: "John" }
        }) {
            ok
            object {
                id
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
    assert result.data["car_create"]["ok"] is True
    assert len(result.data["car_create"]["object"]["id"]) == 36  # lenght of an UUID


@pytest.mark.asyncio
async def test_create_object_with_single_relationship_flap_property(default_branch, car_person_schema):

    Node("Person").new(name="John", height=180).save()

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
        graphene.Schema(query=get_gql_query(), mutation=get_gql_mutation(), auto_camelcase=False).graphql_schema,
        source=query,
        context_value={},
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert result.data["car_create"]["ok"] is True
    assert len(result.data["car_create"]["object"]["id"]) == 36

    car = NodeManager.get_one(result.data["car_create"]["object"]["id"])
    assert car.owner.get().is_protected == True


@pytest.mark.asyncio
async def test_create_object_with_multiple_relationships(default_branch, fruit_tag_schema):

    t1 = Node("Tag").new(name="tag1").save()
    t2 = Node("Tag").new(name="tag2").save()
    t3 = Node("Tag").new(name="tag3").save()

    query = """
    mutation {
        fruit_create(data: {
            name: { value: "apple" },
            tags: [ {id: "tag1" }, {id: "tag2" }, {id: "tag3" } ]
        }) {
            ok
            object {
                id
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
    assert result.data["fruit_create"]["ok"] is True
    assert len(result.data["fruit_create"]["object"]["id"]) == 36  # lenght of an UUID

    fruit = NodeManager.get_one(result.data["fruit_create"]["object"]["id"])
    assert len(fruit.tags.get()) == 3


@pytest.mark.asyncio
async def test_create_object_with_multiple_relationships_flag_property(default_branch, fruit_tag_schema):

    t1 = Node("Tag").new(name="tag1").save()
    t2 = Node("Tag").new(name="tag2").save()
    t3 = Node("Tag").new(name="tag3").save()

    query = """
    mutation {
        fruit_create(data: {
            name: { value: "apple" },
            tags: [
                { id: "tag1", _relation__is_protected: true },
                { id: "tag2", _relation__is_protected: true },
                { id: "tag3", _relation__is_protected: true }
            ]
        }) {
            ok
            object {
                id
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
    assert result.data["fruit_create"]["ok"] is True
    assert len(result.data["fruit_create"]["object"]["id"]) == 36  # lenght of an UUID

    fruit = NodeManager.get_one(result.data["fruit_create"]["object"]["id"])
    rels = fruit.tags.get()
    assert len(rels) == 3
    assert rels[0].is_protected is True
    assert rels[1].is_protected is True
    assert rels[2].is_protected is True


@pytest.mark.asyncio
async def test_create_person_not_valid(default_branch, car_person_schema):

    query = """
    mutation {
        person_create(data: {name: { value: "John"}, height: {value: "182"}}) {
            ok
            object {
                id
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

    assert len(result.errors) == 1
    assert "Int cannot represent non-integer value" in result.errors[0].message
