from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, replace
from datetime import datetime
from typing import TYPE_CHECKING, Any

import pytest

from infrahub.core.constants import RelationshipDirection
from infrahub.core.node import Node
from infrahub.graphql.cost.statistics_store import StatisticsStore
from infrahub.graphql.cost.tasks import refresh_query_cost_statistics
from infrahub.graphql.initialization import prepare_graphql_params
from infrahub.services import InfrahubServices
from tests.component.graphql.cost.helpers import StatisticsUnreachableCache
from tests.helpers.db_query_counter import CountingInfrahubDatabase
from tests.helpers.graphql import graphql, graphql_query

if TYPE_CHECKING:
    from graphql import ExecutionResult

    from infrahub.auth.session import AccountSession
    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase
    from tests.adapters.cache import MemoryCache

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


COST_ESTIMATE_QUERY = """
query ($q: String!, $variables: GenericScalar) {
  InfrahubGraphQLQueryReport(query: $q, variables: $variables) {
    cost_estimate {
      mode
      statistics { branch computed_at version }
      fields {
        path
        kind
        relationship_identifier
        cardinality
        expected { nodes resolver_calls database_rows }
        worst_case { nodes resolver_calls database_rows }
        source
        reason
      }
    }
  }
}
"""

TARGETS_ONLY_QUERY = """
query ($q: String!, $variables: GenericScalar) {
  InfrahubGraphQLQueryReport(query: $q, variables: $variables) {
    targets_unique_nodes
  }
}
"""

CARS_OF_PERSON_QUERY = """
query ($name: String!) {
  TestPerson(name__value: $name) {
    edges {
      node {
        name { value }
        cars { edges { node { name { value } owner { node { name { value } } } } } }
      }
    }
  }
}
"""

PERSONS_QUERY = "query { TestPerson { edges { node { name { value } } } } }"

CARS_OF_PERSONS_BY_ID_QUERY = """
query {
  TestPerson(ids: ["%s"]) {
    edges { node { cars { edges { node { name { value } } } } } }
  }
}
"""

PERSON_MUTATION = 'mutation { TestPersonCreate(data: {name: {value: "Dan"}}) { ok } }'

CARS_BY_PERSON = {"Alice": 0, "Bob": 2, "Carol": 5}


@pytest.fixture
async def car_fleet(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    car_person_schema: SchemaBranch,
    create_test_admin: Node,
    default_permission_backend: None,
) -> dict[str, Node]:
    """Persons owning the cars of `CARS_BY_PERSON`, by name."""
    persons: dict[str, Node] = {}
    for person_name, car_count in CARS_BY_PERSON.items():
        person = await Node.init(db=db, schema="TestPerson")
        await person.new(db=db, name=person_name)
        await person.save(db=db)
        persons[person_name] = person
        for index in range(car_count):
            car = await Node.init(db=db, schema="TestCar")
            await car.new(db=db, name=f"{person_name.lower()}-{index}", owner=person)
            await car.save(db=db)
    return persons


@pytest.fixture
async def car_fleet_with_statistics(car_fleet: dict[str, Node], memory_cache: MemoryCache) -> dict[str, Node]:
    """The persons of `car_fleet`, with the statistics refreshed on their data."""
    await refresh_query_cost_statistics()
    return car_fleet


@dataclass
class ReportRun:
    result: ExecutionResult
    query_counts: Counter[str]
    """Database queries the report ran, by query name."""


async def run_report(
    db: InfrahubDatabase,
    branch: Branch,
    account_session: AccountSession,
    cache: MemoryCache,
    analyzed_query: str,
    variables: dict[str, Any] | list[str] | None,
    report_query: str = COST_ESTIMATE_QUERY,
) -> ReportRun:
    """Run the report and count the database queries of its execution, after the account's permissions are loaded."""
    branch.update_schema_hash()
    graphql_params = await prepare_graphql_params(
        db=db, branch=branch, account_session=account_session, service=await InfrahubServices.new(cache=cache)
    )
    counting_db = CountingInfrahubDatabase.from_db(db=db)
    variable_values: dict[str, Any] = {"q": analyzed_query}
    if variables is not None:
        variable_values["variables"] = variables
    result = await graphql(
        schema=graphql_params.schema,
        source=report_query,
        context_value=replace(graphql_params.context, db=counting_db),
        variable_values=variable_values,
    )
    return ReportRun(result=result, query_counts=counting_db.query_counts)


def cost_estimate_of(run: ReportRun) -> dict[str, Any]:
    assert not run.result.errors, f"Unexpected errors: {run.result.errors}"
    assert run.result.data
    return run.result.data["InfrahubGraphQLQueryReport"]["cost_estimate"]


async def test_cost_estimate_with_variables_counts_the_first_step(
    db: InfrahubDatabase,
    default_branch: Branch,
    session_admin: AccountSession,
    memory_cache: MemoryCache,
    car_fleet_with_statistics: dict[str, Node],
) -> None:
    run = await run_report(
        db=db,
        branch=default_branch,
        account_session=session_admin,
        cache=memory_cache,
        analyzed_query=CARS_OF_PERSON_QUERY,
        variables={"name": "Carol"},
    )

    cost_estimate = cost_estimate_of(run=run)
    assert cost_estimate["mode"] == "COUNTED_FIRST_STEP"
    # Each node reads a row for itself, one for each selected attribute and cardinality-one relationship, and one
    # more under a cardinality-many field; Carol owns 5 cars, and each car has one owner.
    assert cost_estimate["fields"] == [
        {
            "path": "TestPerson",
            "kind": "TestPerson",
            "relationship_identifier": None,
            "cardinality": "MANY",
            "expected": {"nodes": 1, "resolver_calls": 1, "database_rows": 3},
            "worst_case": {"nodes": 1, "resolver_calls": 1, "database_rows": 3},
            "source": "COUNTED",
            "reason": None,
        },
        {
            "path": "TestPerson/cars",
            "kind": "TestCar",
            "relationship_identifier": "testcar__testperson",
            "cardinality": "MANY",
            "expected": {"nodes": 5, "resolver_calls": 1, "database_rows": 20},
            "worst_case": {"nodes": 5, "resolver_calls": 1, "database_rows": 20},
            "source": "COUNTED",
            "reason": None,
        },
        {
            "path": "TestPerson/cars/owner",
            "kind": "TestPerson",
            "relationship_identifier": "testcar__testperson",
            "cardinality": "ONE",
            "expected": {"nodes": 5, "resolver_calls": 5, "database_rows": 10},
            "worst_case": {"nodes": 5, "resolver_calls": 5, "database_rows": 10},
            "source": "STATISTICS",
            "reason": None,
        },
    ]
    assert run.query_counts["graphql-cost-first-step-nodes"] == 1
    assert run.query_counts["graphql-cost-first-step-peer-count"] == 1


async def test_cost_estimate_without_variables_reads_only_the_label_counts(
    db: InfrahubDatabase,
    default_branch: Branch,
    session_admin: AccountSession,
    memory_cache: MemoryCache,
    car_fleet_with_statistics: dict[str, Node],
) -> None:
    run = await run_report(
        db=db,
        branch=default_branch,
        account_session=session_admin,
        cache=memory_cache,
        analyzed_query=CARS_OF_PERSON_QUERY,
        variables=None,
    )

    cost_estimate = cost_estimate_of(run=run)
    assert cost_estimate["mode"] == "STATISTICS_ONLY"
    assert [(field["path"], field["source"]) for field in cost_estimate["fields"]] == [
        ("TestPerson", "STATISTICS"),
        ("TestPerson/cars", "STATISTICS"),
        ("TestPerson/cars/owner", "STATISTICS"),
    ]
    assert run.query_counts == Counter({"graphql-cost-kind-label-count": 1})


async def test_cost_estimate_with_empty_variables_counts_a_query_without_variables(
    db: InfrahubDatabase,
    default_branch: Branch,
    session_admin: AccountSession,
    memory_cache: MemoryCache,
    car_fleet_with_statistics: dict[str, Node],
) -> None:
    run = await run_report(
        db=db,
        branch=default_branch,
        account_session=session_admin,
        cache=memory_cache,
        analyzed_query=PERSONS_QUERY,
        variables={},
    )

    cost_estimate = cost_estimate_of(run=run)
    assert cost_estimate["mode"] == "COUNTED_FIRST_STEP"
    assert cost_estimate["fields"] == [
        {
            "path": "TestPerson",
            "kind": "TestPerson",
            "relationship_identifier": None,
            "cardinality": "MANY",
            "expected": {"nodes": 3, "resolver_calls": 1, "database_rows": 9},
            "worst_case": {"nodes": 3, "resolver_calls": 1, "database_rows": 9},
            "source": "COUNTED",
            "reason": None,
        }
    ]
    assert run.query_counts["graphql-cost-first-step-nodes"] == 1


async def test_cost_estimate_states_the_branch_and_time_of_the_statistics(
    db: InfrahubDatabase,
    default_branch: Branch,
    session_admin: AccountSession,
    memory_cache: MemoryCache,
    car_fleet_with_statistics: dict[str, Node],
) -> None:
    pointer = await StatisticsStore(cache=memory_cache).read_pointer()
    assert pointer is not None

    run = await run_report(
        db=db,
        branch=default_branch,
        account_session=session_admin,
        cache=memory_cache,
        analyzed_query=PERSONS_QUERY,
        variables=None,
    )

    statistics = cost_estimate_of(run=run)["statistics"]
    assert (statistics["branch"], statistics["version"]) == ("main", 1)
    assert datetime.fromisoformat(statistics["computed_at"]) == pointer.computed_at


async def test_statistics_only_estimate_uses_the_stored_peer_count_of_a_listed_node(
    db: InfrahubDatabase,
    default_branch: Branch,
    session_admin: AccountSession,
    memory_cache: MemoryCache,
    car_fleet_with_statistics: dict[str, Node],
) -> None:
    carol_id = car_fleet_with_statistics["Carol"].id
    store = StatisticsStore(cache=memory_cache)
    pointer = await store.read_pointer()
    assert pointer is not None
    person_statistics = (await store.read_kinds(version=pointer.version, kinds=["TestPerson"]))["TestPerson"]
    cars_side = person_statistics.side(identifier="testcar__testperson", direction=RelationshipDirection.INBOUND)
    assert cars_side is not None
    assert {node.node_id: node.peers for node in cars_side.top_nodes}[carol_id] == 5

    run = await run_report(
        db=db,
        branch=default_branch,
        account_session=session_admin,
        cache=memory_cache,
        analyzed_query=CARS_OF_PERSONS_BY_ID_QUERY % carol_id,
        variables=None,
    )

    cost_estimate = cost_estimate_of(run=run)
    assert cost_estimate["mode"] == "STATISTICS_ONLY"
    # The mean of the persons, 7 cars for 3 persons, would give 2 cars.
    assert {field["path"]: field for field in cost_estimate["fields"]}["TestPerson/cars"] == {
        "path": "TestPerson/cars",
        "kind": "TestCar",
        "relationship_identifier": "testcar__testperson",
        "cardinality": "MANY",
        "expected": {"nodes": 5, "resolver_calls": 1, "database_rows": 15},
        "worst_case": {"nodes": 5, "resolver_calls": 1, "database_rows": 15},
        "source": "STATISTICS",
        "reason": None,
    }


async def test_cost_estimate_has_no_statistics_before_the_first_refresh(
    db: InfrahubDatabase,
    default_branch: Branch,
    session_admin: AccountSession,
    memory_cache: MemoryCache,
    car_fleet: dict[str, Node],
) -> None:
    run = await run_report(
        db=db,
        branch=default_branch,
        account_session=session_admin,
        cache=memory_cache,
        analyzed_query=PERSONS_QUERY,
        variables=None,
    )

    cost_estimate = cost_estimate_of(run=run)
    assert (cost_estimate["mode"], cost_estimate["statistics"]) == ("STATISTICS_ONLY", None)
    assert [
        (field["path"], field["expected"], field["source"], field["reason"]) for field in cost_estimate["fields"]
    ] == [("TestPerson", None, None, "no statistics")]


async def test_cost_estimate_of_a_mutation_is_an_error(
    db: InfrahubDatabase,
    default_branch: Branch,
    session_admin: AccountSession,
    memory_cache: MemoryCache,
    car_fleet: dict[str, Node],
) -> None:
    run = await run_report(
        db=db,
        branch=default_branch,
        account_session=session_admin,
        cache=memory_cache,
        analyzed_query=PERSON_MUTATION,
        variables={},
    )

    assert run.result.data is None
    assert run.result.errors
    assert [error.message for error in run.result.errors] == ["The cost estimate covers queries only."]
    assert run.query_counts == Counter()


async def test_cost_estimate_returns_the_coercion_error_of_a_variable_of_the_wrong_type(
    db: InfrahubDatabase,
    default_branch: Branch,
    session_admin: AccountSession,
    memory_cache: MemoryCache,
    car_fleet_with_statistics: dict[str, Node],
) -> None:
    run = await run_report(
        db=db,
        branch=default_branch,
        account_session=session_admin,
        cache=memory_cache,
        analyzed_query=CARS_OF_PERSON_QUERY,
        variables={"name": 5},
    )

    assert run.result.data is None
    assert run.result.errors
    assert [error.message for error in run.result.errors] == [
        "Variable '$name' got invalid value 5; String cannot represent a non string value: 5"
    ]


async def test_cost_estimate_returns_an_error_when_the_variables_are_not_an_object(
    db: InfrahubDatabase,
    default_branch: Branch,
    session_admin: AccountSession,
    memory_cache: MemoryCache,
    car_fleet_with_statistics: dict[str, Node],
) -> None:
    run = await run_report(
        db=db,
        branch=default_branch,
        account_session=session_admin,
        cache=memory_cache,
        analyzed_query=CARS_OF_PERSON_QUERY,
        variables=["Carol"],
    )

    assert run.result.data is None
    assert run.result.errors
    assert [error.message for error in run.result.errors] == [
        "The variables argument must be an object that maps each variable name to its value."
    ]
    assert run.query_counts == Counter()


async def test_cost_estimate_returns_an_error_when_the_statistics_cannot_be_read(
    db: InfrahubDatabase,
    default_branch: Branch,
    session_admin: AccountSession,
    car_fleet: dict[str, Node],
) -> None:
    run = await run_report(
        db=db,
        branch=default_branch,
        account_session=session_admin,
        cache=StatisticsUnreachableCache(),
        analyzed_query=PERSONS_QUERY,
        variables=None,
    )

    assert run.result.data is None
    assert run.result.errors
    assert [error.message for error in run.result.errors] == ["cache unreachable"]


async def test_selecting_only_targets_unique_nodes_runs_no_query(
    db: InfrahubDatabase,
    default_branch: Branch,
    session_admin: AccountSession,
    memory_cache: MemoryCache,
    car_fleet_with_statistics: dict[str, Node],
) -> None:
    run = await run_report(
        db=db,
        branch=default_branch,
        account_session=session_admin,
        cache=memory_cache,
        analyzed_query=CARS_OF_PERSON_QUERY,
        variables={"name": "Carol"},
        report_query=TARGETS_ONLY_QUERY,
    )

    assert not run.result.errors
    assert run.result.data == {"InfrahubGraphQLQueryReport": {"targets_unique_nodes": True}}
    assert run.query_counts == Counter()
