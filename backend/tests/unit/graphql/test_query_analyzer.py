from graphql import DocumentNode, GraphQLSchema

from infrahub.core.branch import Branch
from infrahub.core.constants import InfrahubKind
from infrahub.database import InfrahubDatabase
from infrahub.graphql import prepare_graphql_params
from infrahub.graphql.analyzer import InfrahubGraphQLQueryAnalyzer


async def test_analyzer_init_with_schema(
    db: InfrahubDatabase, default_branch: Branch, car_person_schema_generics, query_01: str, bad_query_01: str
):
    gql_params = prepare_graphql_params(db=db, include_subscription=False, branch=default_branch)
    gqa = InfrahubGraphQLQueryAnalyzer(query=query_01, schema=gql_params.schema, branch=default_branch)
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
    gql_params = prepare_graphql_params(db=db, include_subscription=False, branch=default_branch)
    gqa = InfrahubGraphQLQueryAnalyzer(query=query_01, schema=gql_params.schema, branch=default_branch)
    is_valid, errors = gqa.is_valid
    assert errors is None
    assert is_valid is True

    gqa = InfrahubGraphQLQueryAnalyzer(query=query_03, schema=gql_params.schema, branch=default_branch)
    is_valid, errors = gqa.is_valid
    assert errors is None
    assert is_valid is True

    gqa = InfrahubGraphQLQueryAnalyzer(query=query_02, schema=gql_params.schema, branch=default_branch)
    is_valid, errors = gqa.is_valid
    assert errors is None
    assert is_valid is True

    gqa = InfrahubGraphQLQueryAnalyzer(query=query_04, schema=gql_params.schema, branch=default_branch)
    is_valid, errors = gqa.is_valid
    assert errors is None
    assert is_valid is True

    gqa = InfrahubGraphQLQueryAnalyzer(query=query_introspection, schema=gql_params.schema, branch=default_branch)
    is_valid, errors = gqa.is_valid
    assert errors is None
    assert is_valid is True


async def test_is_valid_core_schema(
    db: InfrahubDatabase,
    default_branch: Branch,
    query_05: str,
    register_core_models_schema,
):
    gql_params = prepare_graphql_params(db=db, include_subscription=False, branch=default_branch)

    gqa = InfrahubGraphQLQueryAnalyzer(query=query_05, schema=gql_params.schema, branch=default_branch)
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
    gql_params = prepare_graphql_params(db=db, include_subscription=False, branch=default_branch)
    gqa = InfrahubGraphQLQueryAnalyzer(query=query_01, schema=gql_params.schema, branch=default_branch)
    assert await gqa.get_models_in_use(types=gql_params.context.types) == {
        "TestCar",
        "TestElectricCar",
        "TestGazCar",
        "TestPerson",
    }

    gqa = InfrahubGraphQLQueryAnalyzer(query=query_03, schema=gql_params.schema, branch=default_branch)
    assert await gqa.get_models_in_use(types=gql_params.context.types) == {
        "TestCar",
        "TestElectricCar",
        "TestGazCar",
        "TestPerson",
    }

    gqa = InfrahubGraphQLQueryAnalyzer(query=query_02, schema=gql_params.schema, branch=default_branch)
    assert await gqa.get_models_in_use(types=gql_params.context.types) == {
        InfrahubKind.GRAPHQLQUERYGROUP,
        InfrahubKind.GENERICGROUP,
        InfrahubKind.STANDARDGROUP,
        "TestCar",
        "TestElectricCar",
        "TestGazCar",
        "TestPerson",
    }
