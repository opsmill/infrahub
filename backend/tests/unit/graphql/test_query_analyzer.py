import pytest
from graphql import DocumentNode, GraphQLSchema, OperationType
from graphql.error import GraphQLSyntaxError
from neo4j import AsyncSession

from infrahub.core.branch import Branch
from infrahub.graphql import generate_graphql_schema
from infrahub.graphql.analyzer import GraphQLQueryAnalyzer


async def test_analyzer_init_query_only(query_01, bad_query_01):
    gqa = GraphQLQueryAnalyzer(query=query_01)
    assert isinstance(gqa.document, DocumentNode)

    with pytest.raises(GraphQLSyntaxError):
        gqa = GraphQLQueryAnalyzer(query=bad_query_01)


async def test_analyzer_init_with_schema(
    session: AsyncSession, default_branch: Branch, car_person_schema_generics, query_01: str, bad_query_01: str
):
    schema = await generate_graphql_schema(session=session, include_subscription=False, branch=default_branch)

    gqa = GraphQLQueryAnalyzer(query=query_01, schema=schema, branch=default_branch)
    assert isinstance(gqa.document, DocumentNode)
    assert isinstance(gqa.schema, GraphQLSchema)


async def test_nbr_queries(query_01: str, query_03: str):
    gqa = GraphQLQueryAnalyzer(query=query_01)
    assert gqa.nbr_queries == 1

    gqa = GraphQLQueryAnalyzer(query=query_03)
    assert gqa.nbr_queries == 2


async def test_query_types(query_01: str, query_03: str):
    gqa = GraphQLQueryAnalyzer(query=query_01)
    assert gqa.query_types == {OperationType.QUERY}

    gqa = GraphQLQueryAnalyzer(query=query_03)
    assert gqa.query_types == {OperationType.QUERY, OperationType.MUTATION}


async def test_is_valid(
    session: AsyncSession,
    default_branch: Branch,
    query_01: str,
    query_02: str,
    query_03: str,
    car_person_schema_generics,
):
    schema = await generate_graphql_schema(session=session, include_subscription=False, branch=default_branch)

    gqa = GraphQLQueryAnalyzer(query=query_01, schema=schema, branch=default_branch)
    is_valid, errors = gqa.is_valid
    assert errors is None
    assert is_valid is True

    gqa = GraphQLQueryAnalyzer(query=query_03, schema=schema, branch=default_branch)
    is_valid, errors = gqa.is_valid
    assert errors is None
    assert is_valid is True

    gqa = GraphQLQueryAnalyzer(query=query_02, schema=schema, branch=default_branch)
    is_valid, errors = gqa.is_valid
    assert errors is None
    assert is_valid is True


async def test_get_fields(query_01: str, query_03: str):
    gqa = GraphQLQueryAnalyzer(query=query_01)
    assert await gqa.get_fields() == {
        "TestPerson": {
            "edges": {
                "node": {
                    "cars": {"edges": {"node": {"name": {"value": None}}}},
                    "name": {"value": None},
                },
            },
        },
    }

    gqa = GraphQLQueryAnalyzer(query=query_03)
    assert await gqa.get_fields() == {
        "TestPerson": {
            "edges": {
                "node": {
                    "cars": {"edges": {"node": {"name": {"value": None}}}},
                    "name": {"value": None},
                },
            },
        },
        "TestPersonCreate": {"object": {"id": None}, "ok": None},
    }


async def test_get_models_in_use(
    session: AsyncSession,
    default_branch: Branch,
    query_01: str,
    query_02: str,
    query_03: str,
    car_person_schema_generics,
):
    schema = await generate_graphql_schema(session=session, include_subscription=False, branch=default_branch)

    gqa = GraphQLQueryAnalyzer(query=query_01, schema=schema, branch=default_branch)
    assert await gqa.get_models_in_use() == {"TestCar", "TestElectricCar", "TestGazCar", "TestPerson"}

    gqa = GraphQLQueryAnalyzer(query=query_03, schema=schema, branch=default_branch)
    assert await gqa.get_models_in_use() == {"TestCar", "TestElectricCar", "TestGazCar", "TestPerson"}

    gqa = GraphQLQueryAnalyzer(query=query_02, schema=schema, branch=default_branch)
    assert await gqa.get_models_in_use() == {
        "CoreGroup",
        "CoreStandardGroup",
        "TestCar",
        "TestElectricCar",
        "TestGazCar",
        "TestPerson",
    }
