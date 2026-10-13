from __future__ import annotations

from copy import copy, deepcopy
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import pytest
from graphql import GraphQLError

from infrahub.core.branch import Branch
from infrahub.core.constants import RelationshipCardinality, RelationshipDirection
from infrahub.core.constants.schema import PARENT_CHILD_IDENTIFIER
from infrahub.core.models import SchemaBranchHash
from infrahub.core.schema import SchemaRoot, core_models, internal_schema
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.graphql.analyzer import InfrahubGraphQLQueryAnalyzer
from infrahub.graphql.cost.models import CostTreeField, RelationshipRef
from infrahub.graphql.cost.recorder import field_path_from_response_keys
from infrahub.graphql.cost.tree import build_cost_tree
from infrahub.graphql.manager import GraphQLSchemaManager
from infrahub.graphql.registry import registry as graphql_registry
from tests.helpers.schema import LOCATION_SCHEMA

if TYPE_CHECKING:
    from collections.abc import Generator

    from graphql import GraphQLSchema

# The car and person schema with two concrete car kinds behind a generic, as the component tests define it.
CAR_PERSON_SCHEMA_GENERICS: dict[str, Any] = {
    "generics": [
        {
            "name": "Car",
            "namespace": "Test",
            "default_filter": "name__value",
            "display_label": "{{ name__value }} {{ color__value }}",
            "order_by": ["name__value"],
            "attributes": [
                {"name": "name", "kind": "Text", "unique": True},
                {"name": "nbr_seats", "kind": "Number"},
                {"name": "color", "kind": "Text", "default_value": "#444444", "max_length": 7},
            ],
            "relationships": [
                {
                    "name": "owner",
                    "peer": "TestPerson",
                    "identifier": "person__car",
                    "optional": False,
                    "cardinality": "one",
                },
                {
                    "name": "previous_owner",
                    "peer": "TestPerson",
                    "identifier": "person_previous__car",
                    "optional": True,
                    "cardinality": "one",
                },
            ],
        },
    ],
    "nodes": [
        {
            "name": "ElectricCar",
            "namespace": "Test",
            "inherit_from": ["TestCar", "CoreArtifactTarget"],
            "attributes": [{"name": "nbr_engine", "kind": "Number"}],
        },
        {
            "name": "GazCar",
            "namespace": "Test",
            "inherit_from": ["TestCar", "CoreArtifactTarget"],
            "attributes": [{"name": "mpg", "kind": "Number"}],
        },
        {
            "name": "Person",
            "namespace": "Test",
            "default_filter": "name__value",
            "display_label": "name__value",
            "attributes": [
                {"name": "name", "kind": "Text", "unique": True},
                {"name": "height", "kind": "Number", "optional": True},
            ],
            "relationships": [{"name": "cars", "peer": "TestCar", "identifier": "person__car", "cardinality": "many"}],
        },
    ],
}

CARS = RelationshipRef(identifier="person__car", direction=RelationshipDirection.BIDIR, name="cars", hierarchical=False)
OWNER = RelationshipRef(
    identifier="person__car", direction=RelationshipDirection.BIDIR, name="owner", hierarchical=False
)
PREVIOUS_OWNER = RelationshipRef(
    identifier="person_previous__car", direction=RelationshipDirection.BIDIR, name="previous_owner", hierarchical=False
)
CAR_KINDS = ("TestElectricCar", "TestGazCar")
LOCATION_KINDS = ("TestingContinent", "TestingCountry", "TestingSite")


@pytest.fixture(scope="module")
def schema_branch() -> SchemaBranch:
    schema_branch = SchemaBranch(cache={}, name="main")
    schema_branch.load_schema(schema=SchemaRoot(**internal_schema))
    schema_branch.load_schema(schema=SchemaRoot(**core_models))
    schema_branch.load_schema(schema=SchemaRoot(**CAR_PERSON_SCHEMA_GENERICS))
    schema_branch.load_schema(schema=deepcopy(LOCATION_SCHEMA))
    schema_branch.process()
    return schema_branch


@pytest.fixture(scope="module")
def graphql_schema(schema_branch: SchemaBranch) -> Generator[GraphQLSchema]:
    saved_state = {
        name: {key: copy(value) for key, value in state.items()} if isinstance(state, dict) else state
        for name, state in vars(graphql_registry).items()
    }
    yield GraphQLSchemaManager(schema=schema_branch).get_graphql_schema()
    for name, state in saved_state.items():
        setattr(graphql_registry, name, state)


def _build_tree(
    query: str,
    schema_branch: SchemaBranch,
    graphql_schema: GraphQLSchema,
    variable_values: dict[str, Any] | None,
    operation_name: str | None = None,
) -> list[CostTreeField]:
    analyzer = InfrahubGraphQLQueryAnalyzer(
        query=query,
        branch=Branch(name="main", schema_hash=SchemaBranchHash(main=schema_branch.get_hash())),
        schema_branch=schema_branch,
        schema=graphql_schema,
        operation_name=operation_name,
    )
    return build_cost_tree(
        analyzer=analyzer, schema=graphql_schema, schema_branch=schema_branch, variable_values=variable_values
    )


def _paths(fields: tuple[CostTreeField, ...] | list[CostTreeField]) -> list[str]:
    paths: list[str] = []
    for tree_field in fields:
        paths.append(tree_field.path)
        paths.extend(_paths(fields=tree_field.children))
    return paths


@dataclass
class TreeFieldsCase:
    name: str
    query: str
    expected: list[CostTreeField]
    variable_values: dict[str, Any] | None = field(default_factory=dict)
    """None reads the query without variables, as a statistics-only estimate does."""


TREE_FIELDS_CASES: list[TreeFieldsCase] = [
    TreeFieldsCase(
        name="attributes_and_cardinality_one_relationships_are_counted",
        query="""
        query {
            TestPerson {
                count
                edges { node {
                    name { value }
                    height { value }
                    display_label
                    cars { edges { node {
                        name { value }
                        owner { node { id } }
                        previous_owner { node { id name { value } } }
                    } } }
                } }
            }
        }
        """,
        expected=[
            CostTreeField(
                path="TestPerson",
                kind="TestPerson",
                concrete_kinds=("TestPerson",),
                parent_kinds=(),
                relationship=None,
                cardinality=RelationshipCardinality.MANY,
                selected_attribute_count=2,
                selected_cardinality_one_count=0,
                selects_count=True,
                selects_nodes=True,
                id_only=False,
                max_matching_nodes=None,
                arguments={},
                children=(
                    CostTreeField(
                        path="TestPerson/cars",
                        kind="TestCar",
                        concrete_kinds=CAR_KINDS,
                        parent_kinds=("TestPerson",),
                        relationship=CARS,
                        cardinality=RelationshipCardinality.MANY,
                        selected_attribute_count=1,
                        selected_cardinality_one_count=2,
                        selects_count=False,
                        selects_nodes=True,
                        id_only=False,
                        max_matching_nodes=None,
                        arguments={},
                        children=(
                            CostTreeField(
                                path="TestPerson/cars/owner",
                                kind="TestPerson",
                                concrete_kinds=("TestPerson",),
                                parent_kinds=CAR_KINDS,
                                relationship=OWNER,
                                cardinality=RelationshipCardinality.ONE,
                                selected_attribute_count=0,
                                selected_cardinality_one_count=0,
                                selects_count=False,
                                selects_nodes=True,
                                id_only=True,
                                max_matching_nodes=None,
                                arguments={},
                                children=(),
                            ),
                            CostTreeField(
                                path="TestPerson/cars/previous_owner",
                                kind="TestPerson",
                                concrete_kinds=("TestPerson",),
                                parent_kinds=CAR_KINDS,
                                relationship=PREVIOUS_OWNER,
                                cardinality=RelationshipCardinality.ONE,
                                selected_attribute_count=1,
                                selected_cardinality_one_count=0,
                                selects_count=False,
                                selects_nodes=True,
                                id_only=False,
                                max_matching_nodes=None,
                                arguments={},
                                children=(),
                            ),
                        ),
                    ),
                ),
            )
        ],
    ),
    TreeFieldsCase(
        name="fields_with_the_same_path_are_merged_and_fragments_narrow_the_parent_kinds",
        query="""
        query {
            TestPerson {
                edges { node {
                    cars { edges { node { name { value } } } }
                    ...PersonCars
                } }
            }
            TestPerson { edges { node { height { value } } } }
        }
        fragment PersonCars on TestPerson {
            cars {
                count
                edges { node {
                    ... on TestGazCar { mpg { value } previous_owner { node { id } } }
                    owner { node { name { value } } }
                } }
            }
        }
        """,
        expected=[
            CostTreeField(
                path="TestPerson",
                kind="TestPerson",
                concrete_kinds=("TestPerson",),
                parent_kinds=(),
                relationship=None,
                cardinality=RelationshipCardinality.MANY,
                selected_attribute_count=1,
                selected_cardinality_one_count=0,
                selects_count=False,
                selects_nodes=True,
                id_only=False,
                max_matching_nodes=None,
                arguments={},
                children=(
                    CostTreeField(
                        path="TestPerson/cars",
                        kind="TestCar",
                        concrete_kinds=CAR_KINDS,
                        parent_kinds=("TestPerson",),
                        relationship=CARS,
                        cardinality=RelationshipCardinality.MANY,
                        selected_attribute_count=2,
                        selected_cardinality_one_count=2,
                        selects_count=True,
                        selects_nodes=True,
                        id_only=False,
                        max_matching_nodes=None,
                        arguments={},
                        children=(
                            CostTreeField(
                                path="TestPerson/cars/owner",
                                kind="TestPerson",
                                concrete_kinds=("TestPerson",),
                                parent_kinds=CAR_KINDS,
                                relationship=OWNER,
                                cardinality=RelationshipCardinality.ONE,
                                selected_attribute_count=1,
                                selected_cardinality_one_count=0,
                                selects_count=False,
                                selects_nodes=True,
                                id_only=False,
                                max_matching_nodes=None,
                                arguments={},
                                children=(),
                            ),
                            CostTreeField(
                                path="TestPerson/cars/previous_owner",
                                kind="TestPerson",
                                concrete_kinds=("TestPerson",),
                                parent_kinds=("TestGazCar",),
                                relationship=PREVIOUS_OWNER,
                                cardinality=RelationshipCardinality.ONE,
                                selected_attribute_count=0,
                                selected_cardinality_one_count=0,
                                selects_count=False,
                                selects_nodes=True,
                                id_only=True,
                                max_matching_nodes=None,
                                arguments={},
                                children=(),
                            ),
                        ),
                    ),
                ),
            )
        ],
    ),
    TreeFieldsCase(
        name="hierarchical_fields_have_no_children_and_count_only_reads_no_node",
        query="""
        query {
            TestingSite { edges { node {
                name { value }
                parent { node { id } }
                ancestors { edges { node {
                    name { value }
                    parent { node { id } }
                    ... on TestingCountry { parent { node { id } } ancestors { count } }
                } } }
                descendants { count }
            } } }
        }
        """,
        expected=[
            CostTreeField(
                path="TestingSite",
                kind="TestingSite",
                concrete_kinds=("TestingSite",),
                parent_kinds=(),
                relationship=None,
                cardinality=RelationshipCardinality.MANY,
                selected_attribute_count=1,
                selected_cardinality_one_count=1,
                selects_count=False,
                selects_nodes=True,
                id_only=False,
                max_matching_nodes=None,
                arguments={},
                children=(
                    CostTreeField(
                        path="TestingSite/parent",
                        kind="TestingCountry",
                        concrete_kinds=("TestingCountry",),
                        parent_kinds=("TestingSite",),
                        relationship=RelationshipRef(
                            identifier=PARENT_CHILD_IDENTIFIER,
                            direction=RelationshipDirection.OUTBOUND,
                            name="parent",
                            hierarchical=False,
                        ),
                        cardinality=RelationshipCardinality.ONE,
                        selected_attribute_count=0,
                        selected_cardinality_one_count=0,
                        selects_count=False,
                        selects_nodes=True,
                        id_only=True,
                        max_matching_nodes=None,
                        arguments={},
                        children=(),
                    ),
                    CostTreeField(
                        path="TestingSite/ancestors",
                        kind="TestingLocation",
                        concrete_kinds=LOCATION_KINDS,
                        parent_kinds=("TestingSite",),
                        relationship=RelationshipRef(
                            identifier=PARENT_CHILD_IDENTIFIER,
                            direction=RelationshipDirection.OUTBOUND,
                            name="ancestors",
                            hierarchical=True,
                        ),
                        cardinality=RelationshipCardinality.MANY,
                        selected_attribute_count=1,
                        selected_cardinality_one_count=0,
                        selects_count=False,
                        selects_nodes=True,
                        id_only=False,
                        max_matching_nodes=None,
                        arguments={},
                        children=(),
                    ),
                    CostTreeField(
                        path="TestingSite/descendants",
                        kind="TestingLocation",
                        concrete_kinds=LOCATION_KINDS,
                        parent_kinds=("TestingSite",),
                        relationship=RelationshipRef(
                            identifier=PARENT_CHILD_IDENTIFIER,
                            direction=RelationshipDirection.INBOUND,
                            name="descendants",
                            hierarchical=True,
                        ),
                        cardinality=RelationshipCardinality.MANY,
                        selected_attribute_count=0,
                        selected_cardinality_one_count=0,
                        selects_count=True,
                        selects_nodes=False,
                        id_only=False,
                        max_matching_nodes=None,
                        arguments={},
                        children=(),
                    ),
                ),
            )
        ],
    ),
    TreeFieldsCase(
        name="arguments_are_coerced_with_the_variable_values",
        query="""
        query People($ids: [ID], $limit: Int, $name: String, $unused: String) {
            TestPerson(ids: $ids, offset: 1, name__value: $unused) {
                edges { node { cars(limit: $limit, name__value: $name) { edges { node { id } } } } }
            }
        }
        """,
        variable_values={"ids": ["person-1", "person-2"], "limit": 2, "name": "volt"},
        expected=[
            CostTreeField(
                path="TestPerson",
                kind="TestPerson",
                concrete_kinds=("TestPerson",),
                parent_kinds=(),
                relationship=None,
                cardinality=RelationshipCardinality.MANY,
                selected_attribute_count=0,
                selected_cardinality_one_count=0,
                selects_count=False,
                selects_nodes=True,
                id_only=False,
                max_matching_nodes=2,
                arguments={"ids": ["person-1", "person-2"], "offset": 1},
                children=(
                    CostTreeField(
                        path="TestPerson/cars",
                        kind="TestCar",
                        concrete_kinds=CAR_KINDS,
                        parent_kinds=("TestPerson",),
                        relationship=CARS,
                        cardinality=RelationshipCardinality.MANY,
                        selected_attribute_count=0,
                        selected_cardinality_one_count=0,
                        selects_count=False,
                        selects_nodes=True,
                        id_only=False,
                        max_matching_nodes=None,
                        arguments={"limit": 2, "name__value": "volt"},
                        children=(),
                    ),
                ),
            )
        ],
    ),
    TreeFieldsCase(
        name="without_variables_only_literal_arguments_are_kept",
        query="""
        query People($id: ID!, $limit: Int) {
            TestPerson(ids: [$id], limit: 5) {
                edges { node { cars(limit: $limit) { count } } }
            }
        }
        """,
        variable_values=None,
        expected=[
            CostTreeField(
                path="TestPerson",
                kind="TestPerson",
                concrete_kinds=("TestPerson",),
                parent_kinds=(),
                relationship=None,
                cardinality=RelationshipCardinality.MANY,
                selected_attribute_count=0,
                selected_cardinality_one_count=0,
                selects_count=False,
                selects_nodes=True,
                id_only=False,
                max_matching_nodes=1,
                arguments={"ids": [None], "limit": 5},
                children=(
                    CostTreeField(
                        path="TestPerson/cars",
                        kind="TestCar",
                        concrete_kinds=CAR_KINDS,
                        parent_kinds=("TestPerson",),
                        relationship=CARS,
                        cardinality=RelationshipCardinality.MANY,
                        selected_attribute_count=0,
                        selected_cardinality_one_count=0,
                        selects_count=True,
                        selects_nodes=False,
                        id_only=False,
                        max_matching_nodes=None,
                        arguments={},
                        children=(),
                    ),
                ),
            )
        ],
    ),
    TreeFieldsCase(
        name="a_pinned_uniqueness_constraint_matches_one_node",
        query="""
        query Person($name: String!) {
            TestPerson(name__value: $name) { edges { node { id } } }
        }
        """,
        variable_values=None,
        expected=[
            CostTreeField(
                path="TestPerson",
                kind="TestPerson",
                concrete_kinds=("TestPerson",),
                parent_kinds=(),
                relationship=None,
                cardinality=RelationshipCardinality.MANY,
                selected_attribute_count=0,
                selected_cardinality_one_count=0,
                selects_count=False,
                selects_nodes=True,
                id_only=False,
                max_matching_nodes=1,
                arguments={},
                children=(),
            )
        ],
    ),
    TreeFieldsCase(
        name="root_fields_without_a_kind_are_left_out",
        query="""
        query {
            InfrahubInfo { version }
            InfrahubGraphQLQueryReport(query: "query { TestPerson { count } }") { targets_unique_nodes }
            TestCar { count }
        }
        """,
        expected=[
            CostTreeField(
                path="TestCar",
                kind="TestCar",
                concrete_kinds=CAR_KINDS,
                parent_kinds=(),
                relationship=None,
                cardinality=RelationshipCardinality.MANY,
                selected_attribute_count=0,
                selected_cardinality_one_count=0,
                selects_count=True,
                selects_nodes=False,
                id_only=False,
                max_matching_nodes=None,
                arguments={},
                children=(),
            )
        ],
    ),
    TreeFieldsCase(
        name="a_mutation_has_no_tree",
        query="""
        mutation { TestPersonCreate(data: { name: { value: "John" } }) { ok object { id } } }
        """,
        expected=[],
    ),
]


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in TREE_FIELDS_CASES])
def test_tree_fields(test_case: TreeFieldsCase, schema_branch: SchemaBranch, graphql_schema: GraphQLSchema) -> None:
    tree = _build_tree(
        query=test_case.query,
        schema_branch=schema_branch,
        graphql_schema=graphql_schema,
        variable_values=test_case.variable_values,
    )

    assert tree == test_case.expected


@dataclass
class RecorderPathsCase:
    name: str
    query: str
    resolver_response_paths: list[list[str | int]]
    """Response path of the first call of each resolver of the query, in the order of the tree."""


RECORDER_PATHS_CASES: list[RecorderPathsCase] = [
    RecorderPathsCase(
        name="nested_relationships",
        query="""
        query { TestPerson { edges { node { cars { edges { node { owner { node { id } } } } } } } } }
        """,
        resolver_response_paths=[
            ["TestPerson"],
            ["TestPerson", "edges", 0, "node", "cars"],
            ["TestPerson", "edges", 0, "node", "cars", "edges", 0, "node", "owner"],
        ],
    ),
    RecorderPathsCase(
        name="aliases_replace_the_field_names",
        query="""
        query {
            people: TestPerson { edges { node {
                owned: cars { edges { node { previous: previous_owner { node { id } } } } }
                cars { count }
            } } }
        }
        """,
        resolver_response_paths=[
            ["people"],
            ["people", "edges", 0, "node", "owned"],
            ["people", "edges", 0, "node", "owned", "edges", 0, "node", "previous"],
            ["people", "edges", 0, "node", "cars"],
        ],
    ),
    RecorderPathsCase(
        name="aliased_edges_and_node_levels_stay_in_the_path",
        query="""
        query { TestPerson { all: edges { person: node { cars { edges { node { id } } } } } } }
        """,
        resolver_response_paths=[
            ["TestPerson"],
            ["TestPerson", "all", 0, "person", "cars"],
        ],
    ),
    RecorderPathsCase(
        name="a_field_aliased_node_shares_the_path_of_its_parent",
        query="""
        query { TestPerson { edges { node { node: cars { edges { node { id } } } } } } }
        """,
        resolver_response_paths=[
            ["TestPerson"],
            ["TestPerson", "edges", 0, "node", "node"],
        ],
    ),
    RecorderPathsCase(
        name="fragments_add_no_level",
        query="""
        query {
            TestPerson { edges { node { ...PersonCars } } }
        }
        fragment PersonCars on TestPerson {
            cars { edges { node { ... on TestGazCar { previous_owner { node { id } } } } } }
        }
        """,
        resolver_response_paths=[
            ["TestPerson"],
            ["TestPerson", "edges", 0, "node", "cars"],
            ["TestPerson", "edges", 0, "node", "cars", "edges", 0, "node", "previous_owner"],
        ],
    ),
]


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in RECORDER_PATHS_CASES])
def test_paths_equal_the_paths_the_recorder_computes(
    test_case: RecorderPathsCase, schema_branch: SchemaBranch, graphql_schema: GraphQLSchema
) -> None:
    tree = _build_tree(
        query=test_case.query, schema_branch=schema_branch, graphql_schema=graphql_schema, variable_values={}
    )

    assert _paths(fields=tree) == [
        field_path_from_response_keys(keys=keys) for keys in test_case.resolver_response_paths
    ]


def test_only_the_selected_operation_is_read(schema_branch: SchemaBranch, graphql_schema: GraphQLSchema) -> None:
    query = """
    query People { TestPerson { edges { node { cars { count } } } } }
    query Cars { TestCar { edges { node { owner { node { id } } } } } }
    """

    tree = _build_tree(
        query=query,
        schema_branch=schema_branch,
        graphql_schema=graphql_schema,
        variable_values={},
        operation_name="Cars",
    )

    assert _paths(fields=tree) == ["TestCar", "TestCar/owner"]


def test_a_variable_of_the_wrong_type_raises_the_coercion_error(
    schema_branch: SchemaBranch, graphql_schema: GraphQLSchema
) -> None:
    query = "query People($limit: Int) { TestPerson(limit: $limit) { count } }"

    with pytest.raises(GraphQLError, match=r"^Variable '\$limit' got invalid value 'many'") as error:
        _build_tree(
            query=query,
            schema_branch=schema_branch,
            graphql_schema=graphql_schema,
            variable_values={"limit": "many"},
        )

    assert (
        error.value.message
        == "Variable '$limit' got invalid value 'many'; Int cannot represent non-integer value: 'many'"
    )
