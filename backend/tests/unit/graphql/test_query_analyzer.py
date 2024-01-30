from graphql import DocumentNode, GraphQLSchema

from infrahub.core.branch.branch import Branch
from infrahub.core.constants import InfrahubKind
from infrahub.database import InfrahubDatabase
from infrahub.graphql import generate_graphql_schema
from infrahub.graphql.analyzer import InfrahubGraphQLQueryAnalyzer


async def test_analyzer_init_with_schema(
    db: InfrahubDatabase, default_branch: Branch, car_person_schema_generics, query_01: str, bad_query_01: str
):
    schema = await generate_graphql_schema(db=db, include_subscription=False, branch=default_branch)

    gqa = InfrahubGraphQLQueryAnalyzer(query=query_01, schema=schema, branch=default_branch)
    assert isinstance(gqa.document, DocumentNode)
    assert isinstance(gqa.schema, GraphQLSchema)


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

    gqa = InfrahubGraphQLQueryAnalyzer(query=query_01, schema=schema, branch=default_branch)
    is_valid, errors = gqa.is_valid
    assert errors is None
    assert is_valid is True

    gqa = InfrahubGraphQLQueryAnalyzer(query=query_03, schema=schema, branch=default_branch)
    is_valid, errors = gqa.is_valid
    assert errors is None
    assert is_valid is True

    gqa = InfrahubGraphQLQueryAnalyzer(query=query_02, schema=schema, branch=default_branch)
    is_valid, errors = gqa.is_valid
    assert errors is None
    assert is_valid is True

    gqa = InfrahubGraphQLQueryAnalyzer(query=query_04, schema=schema, branch=default_branch)
    is_valid, errors = gqa.is_valid
    assert errors is None
    assert is_valid is True

    gqa = InfrahubGraphQLQueryAnalyzer(query=query_introspection, schema=schema, branch=default_branch)
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

    gqa = InfrahubGraphQLQueryAnalyzer(query=query_05, schema=schema, branch=default_branch)
    is_valid, errors = gqa.is_valid
    assert errors is None
    assert is_valid is True


async def test_get_models_in_use(
    db: InfrahubDatabase,
    default_branch: Branch,
    query_01: str,
    query_02: str,
    query_03: str,
    car_person_schema_generics,
):
    schema = await generate_graphql_schema(db=db, include_subscription=False, branch=default_branch)

    gqa = InfrahubGraphQLQueryAnalyzer(query=query_01, schema=schema, branch=default_branch)
    assert await gqa.get_models_in_use() == {"TestCar", "TestElectricCar", "TestGazCar", "TestPerson"}

    gqa = InfrahubGraphQLQueryAnalyzer(query=query_03, schema=schema, branch=default_branch)
    assert await gqa.get_models_in_use() == {"TestCar", "TestElectricCar", "TestGazCar", "TestPerson"}

    gqa = InfrahubGraphQLQueryAnalyzer(query=query_02, schema=schema, branch=default_branch)
    assert await gqa.get_models_in_use() == {
        InfrahubKind.GRAPHQLQUERYGROUP,
        InfrahubKind.GENERICGROUP,
        InfrahubKind.STANDARDGROUP,
        "TestCar",
        "TestElectricCar",
        "TestGazCar",
        "TestPerson",
    }
