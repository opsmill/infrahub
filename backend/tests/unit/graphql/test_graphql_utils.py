from graphql import parse

from infrahub.core.branch import Branch
from infrahub.core.constants import InfrahubKind
from infrahub.database import InfrahubDatabase
from infrahub.graphql import generate_graphql_schema
from infrahub.graphql.utils import extract_fields, extract_schema_models


async def test_extract_fields(query_01):
    document = parse(query_01)
    expected_response = {
        "TestPerson": {
            "edges": {
                "node": {
                    "cars": {"edges": {"node": {"name": {"value": None}}}},
                    "name": {"value": None},
                },
            },
        },
    }
    assert await extract_fields(document.definitions[0].selection_set) == expected_response


async def test_extract_fields_fragment(query_02):
    document = parse(query_02)

    expected_response = {
        "TestPerson": {
            "edges": {
                "node": {
                    "cars": {
                        "edges": {
                            "node": {
                                "member_of_groups": {
                                    "edges": {"node": {"id": None}},
                                },
                                "mpg": {"is_protected": None, "value": None},
                                "name": {"value": None},
                                "nbr_engine": {"value": None},
                            },
                        },
                    },
                    "name": {"value": None},
                },
            },
        },
    }

    assert await extract_fields(document.definitions[0].selection_set) == expected_response


async def test_schema_models(db: InfrahubDatabase, default_branch: Branch, car_person_schema_generics, query_01: str):
    document = parse(query_01)
    schema = await generate_graphql_schema(db=db, include_subscription=False, branch=default_branch)
    fields = await extract_fields(document.definitions[0].selection_set)

    expected_response = {
        "EdgedTestPerson",
        "NestedEdgedTestCar",
        "NestedPaginatedTestCar",
        "PaginatedTestPerson",
        "TestCar",
        "TestElectricCar",
        "TestGazCar",
        "TestPerson",
    }
    assert await extract_schema_models(fields=fields, schema=schema.query_type, root_schema=schema) == expected_response


async def test_schema_models_generics(
    db: InfrahubDatabase, default_branch: Branch, car_person_schema_generics, query_02: str
):
    document = parse(query_02)
    schema = await generate_graphql_schema(db=db, include_subscription=False, branch=default_branch)
    fields = await extract_fields(document.definitions[0].selection_set)

    expected_response = {
        InfrahubKind.GRAPHQLQUERYGROUP,
        InfrahubKind.GENERICGROUP,
        InfrahubKind.STANDARDGROUP,
        "EdgedTestPerson",
        "NestedEdgedCoreGroup",
        "NestedEdgedTestCar",
        "NestedPaginatedCoreGroup",
        "NestedPaginatedTestCar",
        "PaginatedTestPerson",
        "TestCar",
        "TestElectricCar",
        "TestGazCar",
        "TestPerson",
    }
    assert await extract_schema_models(fields=fields, schema=schema.query_type, root_schema=schema) == expected_response
