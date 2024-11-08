from graphql import GraphQLSchema, parse
from infrahub_sdk.utils import extract_fields

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import InfrahubKind
from infrahub.database import InfrahubDatabase
from infrahub.graphql.analyzer import extract_schema_models
from infrahub.graphql.manager import GraphQLSchemaManager


def generate_graphql_schema(
    db: InfrahubDatabase,  # pylint: disable=unused-argument
    branch: Branch | str,
    include_query: bool = True,
    include_mutation: bool = True,
    include_subscription: bool = True,
    include_types: bool = True,
) -> GraphQLSchema:
    branch = registry.get_branch_from_registry(branch)
    schema = registry.schema.get_schema_branch(name=branch.name)
    return GraphQLSchemaManager(schema=schema).generate(
        include_query=include_query,
        include_mutation=include_mutation,
        include_subscription=include_subscription,
        include_types=include_types,
    )


async def test_schema_models(db: InfrahubDatabase, default_branch: Branch, car_person_schema_generics, query_01: str):
    document = parse(query_01)
    schema = generate_graphql_schema(db=db, include_subscription=False, branch=default_branch)
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
    schema = generate_graphql_schema(db=db, include_subscription=False, branch=default_branch)
    fields = await extract_fields(document.definitions[0].selection_set)

    expected_response = {
        InfrahubKind.GENERATORGROUP,
        InfrahubKind.GRAPHQLQUERYGROUP,
        InfrahubKind.GENERICGROUP,
        InfrahubKind.STANDARDGROUP,
        InfrahubKind.ACCOUNTGROUP,
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
