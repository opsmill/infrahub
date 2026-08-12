from copy import deepcopy
from dataclasses import dataclass

import pytest
from graphql import DocumentNode, GraphQLSchema

from infrahub.core.branch import Branch
from infrahub.core.constants import InfrahubKind
from infrahub.core.registry import registry
from infrahub.core.schema import AttributeSchema, SchemaRoot
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.database import InfrahubDatabase
from infrahub.graphql.analyzer import GraphQLArgument, GraphQLVariable, InfrahubGraphQLQueryAnalyzer, MutateAction
from infrahub.graphql.initialization import prepare_graphql_params
from tests.helpers.schema.color import COLOR
from tests.helpers.schema.tshirt import TSHIRT


async def test_analyzer_init_with_schema(
    db: InfrahubDatabase,
    default_branch: Branch,
    car_person_schema_generics: SchemaRoot,
    query_01: str,
    bad_query_01: str,
) -> None:
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
    car_person_schema_generics: SchemaRoot,
) -> None:
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
    register_core_models_schema: SchemaBranch,
) -> None:
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
    car_person_schema_generics: SchemaRoot,
) -> None:
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


async def test_traversed_kinds(
    db: InfrahubDatabase,
    default_branch: Branch,
    query_01: str,
    car_person_schema_generics: SchemaRoot,
) -> None:
    """Traversed kinds cover what the query reaches through a relationship, roots included when shared.

    A caller mapping a data change back to the query's own targets needs the two apart, because a
    kind read only by following a relationship is never one of those targets. The requested-read map
    keys by kind alone, so a kind read on both paths has to count as traversed: once a change is in
    hand there is no way to tell which path saw it.
    """
    schema_branch = registry.schema.get_schema_branch(name=default_branch.name)
    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=default_branch)

    traversing = InfrahubGraphQLQueryAnalyzer(
        query=query_01, schema=gql_params.schema, branch=default_branch, schema_branch=schema_branch
    )
    assert set(traversing.query_report.requested_read) == {"TestPerson", "TestCar", "TestElectricCar", "TestGazCar"}
    assert traversing.query_report.traversed_kinds == {"TestCar", "TestElectricCar", "TestGazCar"}

    generic_root_query = """
    query {
        TestCar {
            edges {
                node {
                    name { value }
                }
            }
        }
    }
    """
    generic_root = InfrahubGraphQLQueryAnalyzer(
        query=generic_root_query, schema=gql_params.schema, branch=default_branch, schema_branch=schema_branch
    )
    assert generic_root.query_report.traversed_kinds == set()

    shared_kind_query = """
    query {
        TestPerson {
            edges {
                node {
                    name { value }
                    cars { edges { node { owner { node { name { value } } } } } }
                }
            }
        }
    }
    """
    shared_kind = InfrahubGraphQLQueryAnalyzer(
        query=shared_kind_query, schema=gql_params.schema, branch=default_branch, schema_branch=schema_branch
    )
    # TestPerson is the root and is reached again through cars -> owner. Reporting it as traversed is
    # what stops a change on one of those owners from being narrowed away.
    assert "TestPerson" in shared_kind.query_report.traversed_kinds


@dataclass
class RequestedReadCase:
    name: str
    query: str
    expected_fields_by_kind: dict[str, set[str]]


REQUESTED_READ_CASES = [
    RequestedReadCase(
        name="unread_members_of_a_traversed_generic_are_reported_empty",
        # A caller cannot treat presence in the map as proof the query depends on the kind, it has
        # to look at the fields. Reporting the members keeps a permission check able to see them.
        query="""
        query {
            TestPerson {
                edges {
                    node {
                        name { value }
                        cars {
                            edges {
                                node {
                                    ... on TestElectricCar {
                                        nbr_engine { value }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
        """,
        expected_fields_by_kind={
            "TestPerson": {"name", "cars"},
            "TestCar": set(),
            "TestElectricCar": {"nbr_engine"},
            "TestGazCar": set(),
        },
    ),
    RequestedReadCase(
        name="node_properties_are_reported_under_their_schema_name",
        # The query spells it hfid, everything downstream calls it human_friendly_id. Reporting the
        # query spelling would leave each consumer to translate it, and silently match nothing.
        query="""
        query {
            TestPerson {
                edges {
                    node {
                        hfid
                        display_label
                        cars {
                            edges {
                                node {
                                    hfid
                                }
                            }
                        }
                    }
                }
            }
        }
        """,
        expected_fields_by_kind={
            "TestPerson": {"human_friendly_id", "display_label", "cars"},
            "TestCar": {"human_friendly_id"},
            "TestElectricCar": {"human_friendly_id"},
            "TestGazCar": {"human_friendly_id"},
        },
    ),
]


@pytest.mark.parametrize("case", REQUESTED_READ_CASES, ids=lambda case: case.name)
async def test_requested_read(
    db: InfrahubDatabase, default_branch: Branch, car_person_schema_generics: SchemaRoot, case: RequestedReadCase
) -> None:
    """Report every kind the query reaches, and the fields it reads from each."""
    schema_branch = registry.schema.get_schema_branch(name=default_branch.name)
    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=default_branch)

    analyzer = InfrahubGraphQLQueryAnalyzer(
        query=case.query, schema=gql_params.schema, branch=default_branch, schema_branch=schema_branch
    )

    assert {
        kind: access.fields for kind, access in analyzer.query_report.requested_read.items()
    } == case.expected_fields_by_kind


async def test_query_report(
    db: InfrahubDatabase, default_branch: Branch, car_person_schema_generics: SchemaRoot
) -> None:
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

    query_required_id = """
    query TshirtQuery($id: ID!) {
        TestingTShirt(ids: [$id]) {
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

    query_required_ids = """
    query TshirtQuery($ids: [ID!]) {
        TestingTShirt(ids: $ids) {
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

    query_optional_id = """
    query TshirtQuery($id: ID) {
        TestingTShirt(ids: [$id]) {
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

    query_optional_ids = """
    query TshirtQuery($ids: [ID!]) {
        TestingTShirt(ids: $ids) {
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

    gqa_required_id = InfrahubGraphQLQueryAnalyzer(
        query=query_required_id,
        schema=gql_params.schema,
        branch=default_branch,
        schema_branch=schema_branch,
    )

    gqa_required_ids = InfrahubGraphQLQueryAnalyzer(
        query=query_required_ids,
        schema=gql_params.schema,
        branch=default_branch,
        schema_branch=schema_branch,
    )

    gqa_optional_id = InfrahubGraphQLQueryAnalyzer(
        query=query_optional_id,
        schema=gql_params.schema,
        branch=default_branch,
        schema_branch=schema_branch,
    )

    gqa_optional_ids = InfrahubGraphQLQueryAnalyzer(
        query=query_optional_ids,
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
    # Querying by ID is always a single result query if the ID is required
    assert gqa_required_id.query_report.only_has_unique_targets is True
    # Querying by ID is not a single result query if the ID is required but defined as an array
    assert gqa_required_ids.query_report.only_has_unique_targets is False
    # Querying by ID is not always a single result query if the ID is optional
    assert gqa_optional_id.query_report.only_has_unique_targets is False
    # Querying by ID is not always a single result query if the ID is an optional array
    assert gqa_optional_ids.query_report.only_has_unique_targets is False


async def test_query_report_single_target_complex_constraints(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: None
) -> None:
    # TestingTShirtComposite: name + the mandatory single-cardinality `color` relationship
    tshirt_composite = deepcopy(TSHIRT)
    tshirt_composite.name = "TShirtComposite"
    tshirt_composite.uniqueness_constraints = [["name__value", "color"]]

    # TestingTShirtMultiple: two independent single-field uniqueness constraints
    tshirt_multiple = deepcopy(TSHIRT)
    tshirt_multiple.name = "TShirtMultiple"
    tshirt_multiple.attributes.append(AttributeSchema(name="serial", kind="Text", optional=True))
    tshirt_multiple.uniqueness_constraints = [["name__value"], ["serial__value"]]

    # TestingTShirtOverlap: overlapping constraints where one group is a subset of another
    tshirt_overlapping = deepcopy(TSHIRT)
    tshirt_overlapping.name = "TShirtOverlap"
    tshirt_overlapping.attributes.append(AttributeSchema(name="serial_number", kind="Text", optional=True))
    tshirt_overlapping.uniqueness_constraints = [["name__value"], ["name__value", "serial_number__value"]]

    # TestingTShirtRel: uniqueness defined solely on the mandatory single-cardinality relationship
    tshirt_rel = deepcopy(TSHIRT)
    tshirt_rel.name = "TShirtRel"
    tshirt_rel.uniqueness_constraints = [["color"]]

    # TestingTShirtHfid: a human-friendly id enables filtering by `hfid`
    tshirt_hfid = deepcopy(TSHIRT)
    tshirt_hfid.name = "TShirtHfid"
    tshirt_hfid.human_friendly_id = ["name__value"]

    schema_root = SchemaRoot(
        nodes=[COLOR, tshirt_composite, tshirt_multiple, tshirt_overlapping, tshirt_rel, tshirt_hfid]
    )
    registry.schema.register_schema(schema=schema_root, branch=default_branch.name)
    default_branch.update_schema_hash()

    schema_branch = registry.schema.get_schema_branch(name=default_branch.name)
    gql_params = await prepare_graphql_params(db=db, branch=default_branch)

    def analyze(query: str) -> InfrahubGraphQLQueryAnalyzer:
        return InfrahubGraphQLQueryAnalyzer(
            query=query, schema=gql_params.schema, branch=default_branch, schema_branch=schema_branch
        )

    composite_fully_pinned = """
    query ($name: String!, $color: ID!) {
        TestingTShirtComposite(name__value: $name, color__ids: [$color]) {
            edges { node { name { value } } }
        }
    }
    """
    composite_partially_pinned = """
    query ($name: String!) {
        TestingTShirtComposite(name__value: $name) {
            edges { node { name { value } } }
        }
    }
    """
    composite_relationship_list_var = """
    query ($name: String!, $colors: [ID!]) {
        TestingTShirtComposite(name__value: $name, color__ids: $colors) {
            edges { node { name { value } } }
        }
    }
    """
    composite_relationship_required_list_var = """
    query ($name: String!, $colors: [ID!]!) {
        TestingTShirtComposite(name__value: $name, color__ids: $colors) {
            edges { node { name { value } } }
        }
    }
    """
    composite_ids_required_list = """
    query ($ids: [ID!]!) {
        TestingTShirtComposite(ids: $ids) {
            edges { node { name { value } } }
        }
    }
    """
    multiple_one_group_pinned = """
    query ($name: String!) {
        TestingTShirtMultiple(name__value: $name) {
            edges { node { name { value } } }
        }
    }
    """
    multiple_other_group_pinned = """
    query ($serial: String!) {
        TestingTShirtMultiple(serial__value: $serial) {
            edges { node { name { value } } }
        }
    }
    """
    multiple_none_pinned = """
    query ($description: String!) {
        TestingTShirtMultiple(description__value: $description) {
            edges { node { name { value } } }
        }
    }
    """
    overlap_subset_group_pinned = """
    query ($name: String!) {
        TestingTShirtOverlap(name__value: $name) {
            edges { node { name { value } } }
        }
    }
    """
    overlap_full_group_pinned = """
    query ($name: String!, $serial: String!) {
        TestingTShirtOverlap(name__value: $name, serial_number__value: $serial) {
            edges { node { name { value } } }
        }
    }
    """
    overlap_partial_only = """
    query ($serial: String!) {
        TestingTShirtOverlap(serial_number__value: $serial) {
            edges { node { name { value } } }
        }
    }
    """
    relationship_pinned = """
    query ($color: ID!) {
        TestingTShirtRel(color__ids: [$color]) {
            edges { node { name { value } } }
        }
    }
    """
    relationship_optional = """
    query ($color: ID) {
        TestingTShirtRel(color__ids: [$color]) {
            edges { node { name { value } } }
        }
    }
    """
    hfid_pinned = """
    query ($hfid: String!) {
        TestingTShirtHfid(hfid: [$hfid]) {
            edges { node { name { value } } }
        }
    }
    """
    hfid_optional = """
    query ($hfid: String) {
        TestingTShirtHfid(hfid: [$hfid]) {
            edges { node { name { value } } }
        }
    }
    """

    # A composite constraint is a single target only when every component is pinned
    assert analyze(composite_fully_pinned).query_report.only_has_unique_targets is True
    assert analyze(composite_partially_pinned).query_report.only_has_unique_targets is False
    # A relationship component is not pinned by an optional list of ids
    assert analyze(composite_relationship_list_var).query_report.only_has_unique_targets is False
    # A relationship component is not pinned by a required list variable either: the list may carry
    # several ids and match several objects, so it cannot be relied on for a single target
    assert analyze(composite_relationship_required_list_var).query_report.only_has_unique_targets is False
    # The top-level ids selector is driven per target member, so a required list variable there is a single target
    assert analyze(composite_ids_required_list).query_report.only_has_unique_targets is True
    # Satisfying any one of several uniqueness constraints is enough
    assert analyze(multiple_one_group_pinned).query_report.only_has_unique_targets is True
    assert analyze(multiple_other_group_pinned).query_report.only_has_unique_targets is True
    # Filtering on a field that is not part of any uniqueness constraint is not a single target
    assert analyze(multiple_none_pinned).query_report.only_has_unique_targets is False
    # Overlapping constraints [["name__value"], ["name__value", "serial_number__value"]]:
    # satisfying the smaller subset group (name) alone is enough
    assert analyze(overlap_subset_group_pinned).query_report.only_has_unique_targets is True
    # Satisfying the larger group (name + serial_number) is also a single target
    assert analyze(overlap_full_group_pinned).query_report.only_has_unique_targets is True
    # Pinning only serial_number satisfies neither group (it is never a standalone unique key)
    assert analyze(overlap_partial_only).query_report.only_has_unique_targets is False
    # A uniqueness constraint made solely of a single-cardinality relationship can be pinned by id
    assert analyze(relationship_pinned).query_report.only_has_unique_targets is True
    assert analyze(relationship_optional).query_report.only_has_unique_targets is False
    # Filtering by a required human-friendly id pins a single target
    assert analyze(hfid_pinned).query_report.only_has_unique_targets is True
    assert analyze(hfid_optional).query_report.only_has_unique_targets is False
