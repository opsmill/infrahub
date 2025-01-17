from graphql import DocumentNode, GraphQLSchema

from infrahub.core.branch import Branch
from infrahub.core.constants import InfrahubKind
from infrahub.core.registry import registry
from infrahub.database import InfrahubDatabase
from infrahub.graphql.analyzer import InfrahubGraphQLQueryAnalyzer
from infrahub.graphql.initialization import prepare_graphql_params


async def test_analyzer_init_with_schema(
    db: InfrahubDatabase, default_branch: Branch, car_person_schema_generics, query_01: str, bad_query_01: str
):
    schema_branch = registry.schema.get_schema_branch(name=default_branch.name)
    gql_params = await prepare_graphql_params(db=db, include_subscription=False, branch=default_branch)
    gqa = InfrahubGraphQLQueryAnalyzer(
        query=query_01, schema=gql_params.schema, branch=default_branch, schema_branch=schema_branch
    )
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
    schema_branch = registry.schema.get_schema_branch(name=default_branch.name)
    gql_params = await prepare_graphql_params(db=db, include_subscription=False, branch=default_branch)
    gqa = InfrahubGraphQLQueryAnalyzer(
        query=query_01, schema=gql_params.schema, branch=default_branch, schema_branch=schema_branch
    )
    is_valid, errors = gqa.is_valid
    assert errors is None
    assert is_valid is True

    gqa = InfrahubGraphQLQueryAnalyzer(
        query=query_03, schema=gql_params.schema, branch=default_branch, schema_branch=schema_branch
    )
    is_valid, errors = gqa.is_valid
    assert errors is None
    assert is_valid is True

    gqa = InfrahubGraphQLQueryAnalyzer(
        query=query_02, schema=gql_params.schema, branch=default_branch, schema_branch=schema_branch
    )
    is_valid, errors = gqa.is_valid
    assert errors is None
    assert is_valid is True

    gqa = InfrahubGraphQLQueryAnalyzer(
        query=query_04, schema=gql_params.schema, branch=default_branch, schema_branch=schema_branch
    )
    is_valid, errors = gqa.is_valid
    assert errors is None
    assert is_valid is True

    gqa = InfrahubGraphQLQueryAnalyzer(
        query=query_introspection, schema=gql_params.schema, branch=default_branch, schema_branch=schema_branch
    )
    is_valid, errors = gqa.is_valid
    assert errors is None
    assert is_valid is True


async def test_is_valid_core_schema(
    db: InfrahubDatabase,
    default_branch: Branch,
    query_05: str,
    register_core_models_schema,
):
    schema_branch = registry.schema.get_schema_branch(name=default_branch.name)
    gql_params = await prepare_graphql_params(db=db, include_subscription=False, branch=default_branch)

    gqa = InfrahubGraphQLQueryAnalyzer(
        query=query_05, schema=gql_params.schema, branch=default_branch, schema_branch=schema_branch
    )
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
    schema_branch = registry.schema.get_schema_branch(name=default_branch.name)
    gql_params = await prepare_graphql_params(db=db, include_subscription=False, branch=default_branch)
    gqa = InfrahubGraphQLQueryAnalyzer(
        query=query_01, schema=gql_params.schema, branch=default_branch, schema_branch=schema_branch
    )
    assert await gqa.get_models_in_use(types=gql_params.context.types) == {
        "TestCar",
        "TestElectricCar",
        "TestGazCar",
        "TestPerson",
    }
    assert gqa.query_report.impacted_models == [
        "TestCar",
        "TestElectricCar",
        "TestGazCar",
        "TestPerson",
    ]
    assert gqa.query_report.requested_read["TestPerson"].attributes == {"name"}
    assert gqa.query_report.requested_read["TestPerson"].relationships == {"cars"}
    assert gqa.query_report.requested_read["TestCar"].attributes == {"name"}
    assert gqa.query_report.requested_read["TestCar"].relationships == set()
    assert gqa.query_report.requested_read["TestElectricCar"].attributes == {"name"}
    assert gqa.query_report.requested_read["TestElectricCar"].relationships == set()
    assert gqa.query_report.requested_read["TestGazCar"].attributes == {"name"}
    assert gqa.query_report.requested_read["TestGazCar"].relationships == set()

    gqa = InfrahubGraphQLQueryAnalyzer(
        query=query_03, schema=gql_params.schema, branch=default_branch, schema_branch=schema_branch
    )
    assert await gqa.get_models_in_use(types=gql_params.context.types) == {
        "TestCar",
        "TestElectricCar",
        "TestGazCar",
        "TestPerson",
    }
    assert gqa.query_report.impacted_models == [
        "TestCar",
        "TestElectricCar",
        "TestGazCar",
        "TestPerson",
    ]

    gqa = InfrahubGraphQLQueryAnalyzer(
        query=query_02, schema=gql_params.schema, branch=default_branch, schema_branch=schema_branch
    )
    assert await gqa.get_models_in_use(types=gql_params.context.types) == {
        InfrahubKind.GENERATORGROUP,
        InfrahubKind.GRAPHQLQUERYGROUP,
        InfrahubKind.GENERICGROUP,
        InfrahubKind.STANDARDGROUP,
        InfrahubKind.ACCOUNTGROUP,
        "TestCar",
        "TestElectricCar",
        "TestGazCar",
        "TestPerson",
    }
    assert gqa.query_report.impacted_models == [
        InfrahubKind.ACCOUNTGROUP,
        InfrahubKind.GENERATORGROUP,
        InfrahubKind.GRAPHQLQUERYGROUP,
        InfrahubKind.GENERICGROUP,
        InfrahubKind.STANDARDGROUP,
        "TestCar",
        "TestElectricCar",
        "TestGazCar",
        "TestPerson",
    ]
    assert gqa.query_report.requested_read["TestPerson"].attributes == {"name"}
    assert gqa.query_report.requested_read["TestPerson"].relationships == {"cars"}
    assert gqa.query_report.requested_read["TestCar"].attributes == {"name"}
    assert gqa.query_report.requested_read["TestCar"].relationships == set()
    assert gqa.query_report.requested_read["TestElectricCar"].attributes == {"name", "nbr_engine"}
    assert gqa.query_report.requested_read["TestElectricCar"].relationships == {"member_of_groups"}
    assert gqa.query_report.requested_read["TestGazCar"].attributes == {"name", "mpg"}
    assert gqa.query_report.requested_read["TestGazCar"].relationships == set()
    assert gqa.query_report.requested_read[InfrahubKind.GENERICGROUP].attributes == set()
    assert gqa.query_report.requested_read[InfrahubKind.GENERICGROUP].relationships == set()


async def test_query_report(db: InfrahubDatabase, default_branch: Branch, car_person_schema_generics):
    schema_branch = registry.schema.get_schema_branch(name=default_branch.name)
    gql_params = await prepare_graphql_params(db=db, include_subscription=False, branch=default_branch)

    mutation_query_no_return_data = """
    mutation {
        TestElectricCar(
            data: {
                name: { value: "Accord" }
                nbr_seats: { value: 5 }
                is_electric: { value: true }
                owner: { id: "John" }
            }
        ) {
            ok
        }
    }
    """
    gqa = InfrahubGraphQLQueryAnalyzer(
        query=mutation_query_no_return_data,
        schema=gql_params.schema,
        branch=default_branch,
        schema_branch=schema_branch,
    )

    # As we only return 'ok' and no data we don't expect to have to read attributes or
    # relationships from the object we created
    assert len(gqa.query_report.requested_read.keys()) == 1
    assert gqa.query_report.requested_read["TestElectricCar"].attributes == set()
    assert gqa.query_report.requested_read["TestElectricCar"].relationships == set()

    mutation_query_with_return_data = """
    mutation {
        TestElectricCar(
            data: {
                name: { value: "Accord" }
                nbr_seats: { value: 5 }
                is_electric: { value: true }
                owner: { id: "John" }
            }
        ) {
            ok
            object {
                id
                name {
                    value
                }
                nbr_seats {
                    value
                }
                owner {
                    node {
                        name {
                            value
                        }
                    }
                }
            }
        }
    }
    """
    gqa = InfrahubGraphQLQueryAnalyzer(
        query=mutation_query_with_return_data,
        schema=gql_params.schema,
        branch=default_branch,
        schema_branch=schema_branch,
    )

    # As we only return data from the object we created and also from a related object
    # we'd need read access from both TestElectricCar and TestPerson
    assert len(gqa.query_report.requested_read.keys()) == 2
    assert gqa.query_report.requested_read["TestElectricCar"].attributes == {"name", "nbr_seats"}
    assert gqa.query_report.requested_read["TestElectricCar"].relationships == {"owner"}
    assert gqa.query_report.requested_read["TestPerson"].attributes == {"name"}
    assert gqa.query_report.requested_read["TestPerson"].relationships == set()

    query_with_source_only_id = """
    query {
        TestElectricCar {
            edges {
                node {
                    name {
                        value
                        source {
                            id
                        }
                    }
                }
            }
        }
    }
    """
    gqa = InfrahubGraphQLQueryAnalyzer(
        query=query_with_source_only_id,
        schema=gql_params.schema,
        branch=default_branch,
        schema_branch=schema_branch,
    )
    # If we only lookup the 'source' property id but not objects themselves
    # we don't expect to need generic read access to all potential objects
    assert len(gqa.query_report.requested_read.keys()) == 1
    assert gqa.query_report.requested_read["TestElectricCar"].attributes == {"name"}
    assert gqa.query_report.requested_read["TestElectricCar"].relationships == set()

    query_with_source_object_lookup = """
    query {
        TestElectricCar {
            edges {
                node {
                    name {
                        value
                        source {
                            id
                            ... on TestPerson {
                                name {
                                    value
                                }
                                height {
                                    value
                                }
                            }
                        }
                    }
                }
            }
        }
    }
    """
    gqa = InfrahubGraphQLQueryAnalyzer(
        query=query_with_source_object_lookup,
        schema=gql_params.schema,
        branch=default_branch,
        schema_branch=schema_branch,
    )
    # If we lookup the 'source' property id and request information about an object
    # attached to the 'source' we require read access to those
    # we don't expect to need generic read access to all potential objects
    assert len(gqa.query_report.requested_read.keys()) == 2
    assert gqa.query_report.requested_read["TestElectricCar"].attributes == {"name"}
    assert gqa.query_report.requested_read["TestElectricCar"].relationships == set()
    assert gqa.query_report.requested_read["TestPerson"].attributes == {"name", "height"}
    assert gqa.query_report.requested_read["TestPerson"].relationships == set()
