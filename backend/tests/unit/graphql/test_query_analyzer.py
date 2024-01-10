import pytest
from graphql import DocumentNode, GraphQLSchema, OperationType
from graphql.error import GraphQLSyntaxError
from infrahub_sdk.analyzer import GraphQLOperation, GraphQLQueryAnalyzer

from infrahub.core.branch import Branch
from infrahub.core.constants import InfrahubKind
from infrahub.database import InfrahubDatabase
from infrahub.graphql import generate_graphql_schema


async def test_analyzer_init_query_only(query_01, bad_query_01):
    gqa = GraphQLQueryAnalyzer(query=query_01)
    assert isinstance(gqa.document, DocumentNode)

    with pytest.raises(GraphQLSyntaxError):
        gqa = GraphQLQueryAnalyzer(query=bad_query_01)


async def test_analyzer_init_with_schema(
    db: InfrahubDatabase, default_branch: Branch, car_person_schema_generics, query_01: str, bad_query_01: str
):
    schema = await generate_graphql_schema(db=db, include_subscription=False, branch=default_branch)

    gqa = GraphQLQueryAnalyzer(query=query_01, schema=schema, branch=default_branch)
    assert isinstance(gqa.document, DocumentNode)
    assert isinstance(gqa.schema, GraphQLSchema)


async def test_nbr_queries(query_01: str, query_03: str):
    gqa = GraphQLQueryAnalyzer(query=query_01)
    assert gqa.nbr_queries == 1

    gqa = GraphQLQueryAnalyzer(query=query_03)
    assert gqa.nbr_queries == 2


async def test_query_types(query_01: str, query_03: str, query_introspection: str):
    gqa = GraphQLQueryAnalyzer(query=query_01)
    assert gqa.operations == [GraphQLOperation(name="TestPerson", operation_type=OperationType.QUERY)]

    gqa = GraphQLQueryAnalyzer(query=query_03)
    assert len(gqa.operations) == 2
    assert GraphQLOperation(name="TestPerson", operation_type=OperationType.QUERY) in gqa.operations
    assert GraphQLOperation(name="TestPersonCreate", operation_type=OperationType.MUTATION) in gqa.operations

    gqa = GraphQLQueryAnalyzer(query=query_introspection)
    assert gqa.operations == [GraphQLOperation(name="__schema", operation_type=OperationType.QUERY)]


async def test_is_valid_simple_schema(
    db: InfrahubDatabase,
    default_branch: Branch,
    query_01: str,
    query_02: str,
    query_03: str,
    query_04: str,
    query_introspection: str,
    car_person_schema_generics,
):
    schema = await generate_graphql_schema(db=db, include_subscription=False, branch=default_branch)

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

    gqa = GraphQLQueryAnalyzer(query=query_04, schema=schema, branch=default_branch)
    is_valid, errors = gqa.is_valid
    assert errors is None
    assert is_valid is True

    gqa = GraphQLQueryAnalyzer(query=query_introspection, schema=schema, branch=default_branch)
    is_valid, errors = gqa.is_valid
    assert errors is None
    assert is_valid is True


async def test_is_valid_core_schema(
    db: InfrahubDatabase,
    default_branch: Branch,
    query_05: str,
    register_core_models_schema,
):
    schema = await generate_graphql_schema(db=db, include_subscription=False, branch=default_branch)

    gqa = GraphQLQueryAnalyzer(query=query_05, schema=schema, branch=default_branch)
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
    db: InfrahubDatabase,
    default_branch: Branch,
    query_01: str,
    query_02: str,
    query_03: str,
    car_person_schema_generics,
):
    schema = await generate_graphql_schema(db=db, include_subscription=False, branch=default_branch)

    gqa = GraphQLQueryAnalyzer(query=query_01, schema=schema, branch=default_branch)
    assert await gqa.get_models_in_use() == {"TestCar", "TestElectricCar", "TestGazCar", "TestPerson"}

    gqa = GraphQLQueryAnalyzer(query=query_03, schema=schema, branch=default_branch)
    assert await gqa.get_models_in_use() == {"TestCar", "TestElectricCar", "TestGazCar", "TestPerson"}

    gqa = GraphQLQueryAnalyzer(query=query_02, schema=schema, branch=default_branch)
    assert await gqa.get_models_in_use() == {
        InfrahubKind.GRAPHQLQUERYGROUP,
        InfrahubKind.GENERICGROUP,
        InfrahubKind.STANDARDGROUP,
        "TestCar",
        "TestElectricCar",
        "TestGazCar",
        "TestPerson",
    }


async def test_calculate_depth(
    query_01: str,
    query_02: str,
    query_03: str,
    query_04: str,
):
    gqa = GraphQLQueryAnalyzer(query=query_01)
    assert await gqa.calculate_depth() == 9

    gqa = GraphQLQueryAnalyzer(query=query_02)
    assert await gqa.calculate_depth() == 11

    gqa = GraphQLQueryAnalyzer(query=query_03)
    assert await gqa.calculate_depth() == 9

    gqa = GraphQLQueryAnalyzer(query=query_04)
    assert await gqa.calculate_depth() == 6


async def test_calculate_height(
    query_01: str,
    query_02: str,
    query_03: str,
    query_04: str,
):
    gqa = GraphQLQueryAnalyzer(query=query_01)
    assert await gqa.calculate_height() == 10

    gqa = GraphQLQueryAnalyzer(query=query_02)
    assert await gqa.calculate_height() == 19

    gqa = GraphQLQueryAnalyzer(query=query_03)
    assert await gqa.calculate_height() == 14

    gqa = GraphQLQueryAnalyzer(query=query_04)
    assert await gqa.calculate_height() == 5


async def test_get_variables(
    query_01: str,
    query_04: str,
    query_05: str,
    query_06: str,
):
    gqa = GraphQLQueryAnalyzer(query=query_01)
    assert gqa.variables == []

    gqa = GraphQLQueryAnalyzer(query=query_04)
    assert [var.dict() for var in gqa.variables] == [
        {"default_value": None, "name": "person", "required": True, "type": "String"}
    ]

    gqa = GraphQLQueryAnalyzer(query=query_05)
    assert [var.dict() for var in gqa.variables] == [
        {"default_value": None, "name": "myvar", "required": False, "type": "String"}
    ]

    gqa = GraphQLQueryAnalyzer(query=query_06)
    assert [var.dict() for var in gqa.variables] == [
        {
            "default_value": None,
            "name": "str1",
            "required": False,
            "type": "String",
        },
        {
            "default_value": "default2",
            "name": "str2",
            "required": False,
            "type": "String",
        },
        {
            "default_value": None,
            "name": "str3",
            "required": True,
            "type": "String",
        },
        {"default_value": None, "name": "int1", "required": False, "type": "Int"},
        {"default_value": 12, "name": "int2", "required": False, "type": "Int"},
        {"default_value": None, "name": "int3", "required": True, "type": "Int"},
        {
            "default_value": None,
            "name": "bool1",
            "required": False,
            "type": "Boolean",
        },
        {
            "default_value": True,
            "name": "bool2",
            "required": False,
            "type": "Boolean",
        },
        {
            "default_value": None,
            "name": "bool3",
            "required": True,
            "type": "Boolean",
        },
    ]
