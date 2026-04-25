from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from tests.helpers.graphql import graphql_query

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase

QUERY = """
query ($q: String!) {
  InfrahubGraphQLQueryReport(query: $q) {
    targets_unique_nodes
  }
}
"""


@dataclass
class UniqueTargetsTestCase:
    analyzed_query: str
    expected: bool
    description: str


UNIQUE_TARGETS_TEST_CASES = [
    UniqueTargetsTestCase(
        description="required variable matching uniqueness constraint",
        analyzed_query="""
            query ($name: String!) {
              TestCar(name__value: $name) {
                edges { node { id } }
              }
            }
        """,
        expected=True,
    ),
    UniqueTargetsTestCase(
        description="hardcoded value matching uniqueness constraint",
        analyzed_query="""
            query {
              TestCar(name__value: "mycar") {
                edges { node { id } }
              }
            }
        """,
        expected=True,
    ),
    UniqueTargetsTestCase(
        description="no filter returns all nodes",
        analyzed_query="""
            query {
              TestCar {
                edges { node { id } }
              }
            }
        """,
        expected=False,
    ),
    UniqueTargetsTestCase(
        description="optional (nullable) variable does not guarantee uniqueness",
        analyzed_query="""
            query ($name: String) {
              TestCar(name__value: $name) {
                edges { node { id } }
              }
            }
        """,
        expected=False,
    ),
]


async def test_targets_unique_nodes(
    db: InfrahubDatabase,
    default_branch: Branch,
    car_person_schema: SchemaBranch,
) -> None:
    assert UNIQUE_TARGETS_TEST_CASES, "No test cases defined for unique targets test"
    for case in UNIQUE_TARGETS_TEST_CASES:
        response = await graphql_query(query=QUERY, db=db, branch=default_branch, variables={"q": case.analyzed_query})

        assert not response.errors, f"Unexpected errors for case '{case.description}': {response.errors}"
        assert response.data
        result = response.data["InfrahubGraphQLQueryReport"]["targets_unique_nodes"]
        assert result is case.expected, f"Case '{case.description}': expected {case.expected}, got {result}"


async def test_error_on_empty_query_string(
    db: InfrahubDatabase,
    default_branch: Branch,
    car_person_schema: SchemaBranch,
) -> None:
    response = await graphql_query(query=QUERY, db=db, branch=default_branch, variables={"q": ""})

    assert response.errors
    error = response.errors[0]
    assert "Syntax Error: Unexpected <EOF>." in error.message
    assert error.locations
    assert error.locations[0].line == 1


async def test_error_on_invalid_graphql_syntax(
    db: InfrahubDatabase,
    default_branch: Branch,
    car_person_schema: SchemaBranch,
) -> None:
    response = await graphql_query(query=QUERY, db=db, branch=default_branch, variables={"q": "not valid graphql {"})

    assert response.errors
    error = response.errors[0]
    assert "Syntax Error: Unexpected Name 'not'." in error.message
    # Locations must point into the analyzed query string (line 1), not the
    # outer wrapper query — proves the inner GraphQLSyntaxError is re-raised
    # rather than wrapped in a fresh, location-less GraphQLError.
    assert error.locations
    assert error.locations[0].line == 1


async def test_error_on_nonexistent_node_type(
    db: InfrahubDatabase,
    default_branch: Branch,
    car_person_schema: SchemaBranch,
) -> None:
    inner_query = "query { NonExistentType123 { edges { node { id } } } }"
    response = await graphql_query(
        query=QUERY,
        db=db,
        branch=default_branch,
        variables={"q": inner_query},
    )

    assert response.errors
    error = response.errors[0]
    assert "Cannot query field 'NonExistentType123' on type 'Query'." in error.message
    assert error.locations
    assert error.locations[0].line == 1
    assert error.locations[0].column == inner_query.index("NonExistentType123") + 1
