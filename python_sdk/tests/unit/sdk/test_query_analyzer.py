import pytest
from graphql import DocumentNode, OperationType
from graphql.error import GraphQLSyntaxError

from infrahub_sdk.analyzer import GraphQLOperation, GraphQLQueryAnalyzer


async def test_analyzer_init_query_only(query_01, bad_query_01):
    gqa = GraphQLQueryAnalyzer(query=query_01)
    assert isinstance(gqa.document, DocumentNode)

    with pytest.raises(GraphQLSyntaxError):
        gqa = GraphQLQueryAnalyzer(query=bad_query_01)


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
