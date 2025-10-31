from graphql import DocumentNode, GraphQLSchema

from infrahub.core.branch import Branch
from infrahub.core.constants import InfrahubKind
from infrahub.core.registry import registry
from infrahub.core.schema import SchemaRoot
from infrahub.database import InfrahubDatabase
from infrahub.graphql.analyzer import GraphQLArgument, GraphQLVariable, InfrahubGraphQLQueryAnalyzer, MutateAction
from infrahub.graphql.initialization import prepare_graphql_params
from tests.helpers.schema.color import COLOR
from tests.helpers.schema.tshirt import TSHIRT


async def test_analyzer_init_with_schema(
    db: InfrahubDatabase, default_branch: Branch, car_person_schema_generics, query_01: str, bad_query_01: str
):
    schema_branch = registry.schema.get_schema_branch(name=default_branch.name)
    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=default_branch)
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
    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=default_branch)
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
    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=default_branch)

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
    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=default_branch)
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
        InfrahubKind.GENERATORAWAREGROUP,
        InfrahubKind.GRAPHQLQUERYGROUP,
        InfrahubKind.GENERICGROUP,
        InfrahubKind.STANDARDGROUP,
        InfrahubKind.ACCOUNTGROUP,
        InfrahubKind.REPOSITORYGROUP,
        "TestCar",
        "TestElectricCar",
        "TestGazCar",
        "TestPerson",
    }
    assert gqa.query_report.impacted_models == [
        InfrahubKind.ACCOUNTGROUP,
        InfrahubKind.GENERATORAWAREGROUP,
        InfrahubKind.GENERATORGROUP,
        InfrahubKind.GRAPHQLQUERYGROUP,
        InfrahubKind.GENERICGROUP,
        InfrahubKind.REPOSITORYGROUP,
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
    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=default_branch)

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
    assert len(gqa.query_report.queries) == 1
    assert len(gqa.query_report.queries[0].arguments) == 1
    assert gqa.query_report.queries[0].arguments[0] == GraphQLArgument(
        name="data",
        value={
            "name": {"value": "Accord"},
            "nbr_seats": {"value": 5},
            "is_electric": {"value": True},
            "owner": {"id": "John"},
        },
        kind="object_value",
    )
    assert gqa.query_report.queries[0].arguments[0].fields == ["is_electric", "name", "nbr_seats", "owner"]

    mutation_query_with_return_data = """
    mutation CarCreator($car_name: String!) {
        TestElectricCarCreate(
            data: {
                name: { value: $car_name }
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
    assert len(gqa.query_report.kind_action_map.keys()) == 2
    assert gqa.query_report.kind_action_map["TestElectricCar"] == {MutateAction.CREATE}
    assert gqa.query_report.kind_action_map["TestPerson"] == {MutateAction.UPDATE}
    assert gqa.query_report.variables == [
        GraphQLVariable(
            name="car_name", type="String", required=True, is_list=False, inner_required=False, default=None
        )
    ]
    assert len(gqa.query_report.queries) == 1
    assert len(gqa.query_report.queries[0].arguments) == 1
    assert gqa.query_report.queries[0].arguments[0] == GraphQLArgument(
        name="data",
        value={
            "name": {"value": "$car_name"},
            "nbr_seats": {"value": 5},
            "is_electric": {"value": True},
            "owner": {"id": "John"},
        },
        kind="object_value",
    )
    assert gqa.query_report.queries[0].arguments[0].fields == ["is_electric", "name", "nbr_seats", "owner"]

    mutation_query_with_simple_return_data = """
    mutation {
        TestElectricCarCreate(
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
            }
        }
    }
    """
    gqa = InfrahubGraphQLQueryAnalyzer(
        query=mutation_query_with_simple_return_data,
        schema=gql_params.schema,
        branch=default_branch,
        schema_branch=schema_branch,
    )

    # As we only return data from the object we created and also from a related object
    # we'd need read access from both TestElectricCar and TestPerson
    assert len(gqa.query_report.requested_read.keys()) == 1
    assert gqa.query_report.requested_read["TestElectricCar"].attributes == {"name", "nbr_seats"}
    assert gqa.query_report.requested_read["TestElectricCar"].relationships == set()
    # Unlike the test case above this one doesn't return data for the owner and as such we don't currently
    # need the update permission on the test person. This is something that we will want to change in the
    # future
    assert len(gqa.query_report.kind_action_map.keys()) == 1
    assert gqa.query_report.kind_action_map["TestElectricCar"] == {MutateAction.CREATE}

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


async def test_query_report_single_target(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: None
) -> None:
    schema_root = SchemaRoot(nodes=[COLOR, TSHIRT])
    registry.schema.register_schema(schema=schema_root, branch=default_branch.name)
    default_branch.update_schema_hash()

    schema_branch = registry.schema.get_schema_branch(name=default_branch.name)

    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=default_branch)

    query_name_variable_required = """
    query TshirtQuery($name: String!) {
        TestingTShirt(name__value: $name) {
            edges {
                node {
                    name {
                        value
                    }
                    color {
                        node {
                            name {
                                value
                            }
                        }
                    }
                }
            }
        }
    }
    """

    query_name_variable_optional = """
    query TshirtQuery($name: String) {
        TestingTShirt(name__value: $name) {
            edges {
                node {
                    name {
                        value
                    }
                    color {
                        node {
                            name {
                                value
                            }
                        }
                    }
                }
            }
        }
    }
    """

    query_name_hardcoded = """
    query TshirtQuery {
        TestingTShirt(name__value: "explorer") {
            edges {
                node {
                    name {
                        value
                    }
                    color {
                        node {
                            name {
                                value
                            }
                        }
                    }
                }
            }
        }
    }
    """

    query_names_hardcoded = """
    query TshirtQuery {
        TestingTShirt(name__values: ["explorer"]) {
            edges {
                node {
                    name {
                        value
                    }
                    color {
                        node {
                            name {
                                value
                            }
                        }
                    }
                }
            }
        }
    }
    """

    query_name_variable_required_extra_nodes = """
    query TshirtQuery($name: String!) {
        TestingTShirt(name__value: $name) {
            edges {
                node {
                    name {
                        value
                    }
                    color {
                        node {
                            name {
                                value
                            }
                        }
                    }
                }
            }
        }
        TestingColor {
            edges {
                node {
                    name {
                        value
                    }
                }
            }
        }
    }
    """

    query_name_variable_required_extra_nodes_required_filter = """
    query TshirtQuery($name: String!) {
        TestingTShirt(name__value: $name) {
            edges {
                node {
                    name {
                        value
                    }
                    color {
                        node {
                            name {
                                value
                            }
                        }
                    }
                }
            }
        }
        TestingColor(name__value: "orange") {
            edges {
                node {
                    name {
                        value
                    }
                }
            }
        }
    }
    """

    gqa_required_name_variable = InfrahubGraphQLQueryAnalyzer(
        query=query_name_variable_required,
        schema=gql_params.schema,
        branch=default_branch,
        schema_branch=schema_branch,
    )
    gqa_optional_name_variable = InfrahubGraphQLQueryAnalyzer(
        query=query_name_variable_optional,
        schema=gql_params.schema,
        branch=default_branch,
        schema_branch=schema_branch,
    )

    gqa_required_name_hardcoded = InfrahubGraphQLQueryAnalyzer(
        query=query_name_hardcoded,
        schema=gql_params.schema,
        branch=default_branch,
        schema_branch=schema_branch,
    )

    gqa_names_hardcoded = InfrahubGraphQLQueryAnalyzer(
        query=query_names_hardcoded,
        schema=gql_params.schema,
        branch=default_branch,
        schema_branch=schema_branch,
    )

    gqa_required_name_variable_extra_query = InfrahubGraphQLQueryAnalyzer(
        query=query_name_variable_required_extra_nodes,
        schema=gql_params.schema,
        branch=default_branch,
        schema_branch=schema_branch,
    )
    gqa_required_name_variable_extra_query_required = InfrahubGraphQLQueryAnalyzer(
        query=query_name_variable_required_extra_nodes_required_filter,
        schema=gql_params.schema,
        branch=default_branch,
        schema_branch=schema_branch,
    )

    # A required variable matching a uniqueness constraint should indicate a single result query
    assert gqa_required_name_variable.query_report.only_has_unique_targets is True
    # If the variable is optional it's not a single result query
    assert gqa_optional_name_variable.query_report.only_has_unique_targets is False
    # A hardcoded name matching the uniqueness constraint would match a single result query
    assert gqa_required_name_hardcoded.query_report.only_has_unique_targets is True
    # While name_value is a uniqueness constraint when querying with "names_values" it will not be a single result query
    assert gqa_names_hardcoded.query_report.only_has_unique_targets is False
    # Adding a new model indicates that there this will not be a single result query
    assert gqa_required_name_variable_extra_query.query_report.only_has_unique_targets is False
    # Adding a uniqueness constraint to the second query let's us use it as a single result query again
    assert gqa_required_name_variable_extra_query_required.query_report.only_has_unique_targets is True
