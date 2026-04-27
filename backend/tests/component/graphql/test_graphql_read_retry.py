"""Component tests for GraphQL read resolver retry on transient Neo4j errors.

These tests simulate Neo4j server-side Bolt thread pool exhaustion by spinning up
a dedicated Neo4j container with server.bolt.thread_pool_max_size=10 and firing
concurrent queries that hit many-cardinality relationship resolvers.

All fixtures are module-scoped so xdist (--dist loadscope) runs them on a single
worker and the dedicated container is stopped as soon as the module finishes.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, AsyncGenerator, Generator

import pytest
from neo4j.exceptions import TransientError

from infrahub import config
from infrahub.core import registry
from infrahub.core.initialization import add_indexes
from infrahub.core.node import Node
from infrahub.database import InfrahubDatabase, get_db
from infrahub.graphql.initialization import prepare_graphql_params
from tests.conftest import (
    do_car_person_schema_unregistered,
    do_data_schema,
    do_default_branch,
    do_empty_database,
    do_group_schema,
    do_local_storage_dir,
    do_reset_registry,
)
from tests.helpers.constants import INFRAHUB_USE_TEST_CONTAINERS, NEO4J_IMAGE, PORT_BOLT_NEO4J
from tests.helpers.graphql import graphql
from tests.helpers.utils import get_exposed_port, start_neo4j_container

if TYPE_CHECKING:
    from graphql.execution import ExecutionResult

    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch

NUM_CARS = 10

QUERY_MANY_RELATIONSHIP = """
query {
    TestPerson {
        edges {
            node {
                name { value }
                cars {
                    edges {
                        node {
                            name { value }
                        }
                    }
                }
            }
        }
    }
}
"""

# ---------------------------------------------------------------------------
# Module-scoped fixtures for the dedicated small-thread-pool Neo4j container
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def neo4j_small_thread_pool(request: pytest.FixtureRequest) -> int:
    """Start a dedicated Neo4j container with a minimal Bolt thread pool (size=10)."""
    if not INFRAHUB_USE_TEST_CONTAINERS:
        pytest.skip("Test containers are disabled")

    container = start_neo4j_container(
        neo4j_image=NEO4J_IMAGE,
        extra_env={"NEO4J_server_bolt_thread__pool__max__size": "10"},
    )
    request.addfinalizer(container.stop)

    return get_exposed_port(container, PORT_BOLT_NEO4J)


@pytest.fixture(scope="module")
async def db_small_thread_pool(
    neo4j_small_thread_pool: int,
) -> AsyncGenerator[InfrahubDatabase, None]:
    """Create an InfrahubDatabase connected to the small-thread-pool Neo4j."""
    original_address = config.SETTINGS.database.address
    original_port = config.SETTINGS.database.port

    config.SETTINGS.database.address = "localhost"
    config.SETTINGS.database.port = neo4j_small_thread_pool

    driver = await get_db(retry=5)
    db = InfrahubDatabase(driver=driver)
    await add_indexes(db=db)

    yield db

    await db.close()
    config.SETTINGS.database.address = original_address
    config.SETTINGS.database.port = original_port


@pytest.fixture(scope="module")
async def default_branch_stp(
    db_small_thread_pool: InfrahubDatabase, tmp_path_factory: pytest.TempPathFactory
) -> Branch:
    """Create default branch on the small-thread-pool DB."""
    tmp_path = tmp_path_factory.mktemp("storage_stp")
    do_local_storage_dir(tmp_path=tmp_path)
    await do_empty_database(db=db_small_thread_pool)
    await do_reset_registry(db=db_small_thread_pool)
    return await do_default_branch(db=db_small_thread_pool)


@pytest.fixture(scope="module")
async def car_person_schema_stp(
    db_small_thread_pool: InfrahubDatabase,
    default_branch_stp: Branch,
) -> SchemaBranch:
    """Register data_schema + node_group_schema + car_person_schema on the small-thread-pool DB."""
    branch = default_branch_stp
    do_data_schema(branch=branch)
    do_group_schema(branch=branch)
    car_person = do_car_person_schema_unregistered()
    return registry.schema.register_schema(schema=car_person, branch=branch.name)


# ---------------------------------------------------------------------------
# Test data fixture
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
async def test_data_stp(
    db_small_thread_pool: InfrahubDatabase,
    default_branch_stp: Branch,
    car_person_schema_stp: SchemaBranch,
) -> None:
    """Create 1 person with multiple cars on the small-thread-pool DB."""
    person_schema = car_person_schema_stp.get_node(name="TestPerson")
    car_schema = car_person_schema_stp.get_node(name="TestCar")

    person = await Node.init(db=db_small_thread_pool, schema=person_schema, branch=default_branch_stp)
    await person.new(db=db_small_thread_pool, name="John", height=180)
    await person.save(db=db_small_thread_pool)

    for i in range(NUM_CARS):
        car = await Node.init(db=db_small_thread_pool, schema=car_schema, branch=default_branch_stp)
        await car.new(db=db_small_thread_pool, name=f"car{i}", nbr_seats=4, is_electric=True, owner=person)
        await car.save(db=db_small_thread_pool)


async def _run_graphql_query(db: InfrahubDatabase, branch: Branch) -> ExecutionResult:
    """Run the many-relationship GraphQL query and return the result."""
    branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=branch)
    return await graphql(
        schema=gql_params.schema,
        source=QUERY_MANY_RELATIONSHIP,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_concurrent_many_relationship_queries_recover_from_pool_exhaustion(
    db_small_thread_pool: InfrahubDatabase,
    default_branch_stp: Branch,
    test_data_stp: None,
) -> None:
    """Test that concurrent GraphQL queries hitting many-relationship resolvers
    recover from Neo4j server thread pool exhaustion via retry_db_transaction."""
    num_concurrent = 10
    results = await asyncio.gather(
        *[_run_graphql_query(db=db_small_thread_pool, branch=default_branch_stp) for _ in range(num_concurrent)],
        return_exceptions=True,
    )

    successful = [r for r in results if not isinstance(r, BaseException) and r.errors is None]
    assert len(successful) == num_concurrent, (
        f"Expected all {num_concurrent} queries to succeed, but only {len(successful)} did. "
        f"Errors: {[r.errors if hasattr(r, 'errors') else str(r) for r in results if r not in successful]}"
    )

    for result in successful:
        person_data = result.data["TestPerson"]["edges"][0]["node"]
        assert person_data["name"]["value"] == "John"
        assert len(person_data["cars"]["edges"]) == NUM_CARS


@pytest.fixture
def _disable_retries() -> Generator[None, None, None]:
    """Set retry_limit=1 (no retries) and restore after the test."""
    original = config.SETTINGS.database.retry_limit
    config.SETTINGS.database.retry_limit = 1
    yield
    config.SETTINGS.database.retry_limit = original


@pytest.mark.skip(reason="Reproduction test for issue #8696 - not suitable for CI as it can be flaky")
@pytest.mark.usefixtures("_disable_retries")
async def test_concurrent_queries_fail_without_retries(
    db_small_thread_pool: InfrahubDatabase,
    default_branch_stp: Branch,
    test_data_stp: None,
) -> None:
    """Test that without retries, concurrent queries on a small thread pool fail
    with TransientError, proving the retry mechanism is needed."""
    # Must be significantly higher than thread_pool_max_size to guarantee exhaustion.
    # Each coroutine makes multiple sequential DB calls; we need enough concurrent
    # coroutines so the total in-flight DB requests exceed the server's thread pool.
    num_concurrent = 50
    results = await asyncio.gather(
        *[_run_graphql_query(db=db_small_thread_pool, branch=default_branch_stp) for _ in range(num_concurrent)],
        return_exceptions=True,
    )

    # Collect TransientError failures: either raw exceptions or GraphQL errors wrapping TransientError
    transient_failures = []
    for r in results:
        if isinstance(r, TransientError):
            transient_failures.append(r)
        elif hasattr(r, "errors") and r.errors:
            for err in r.errors:
                if isinstance(getattr(err, "original_error", None), TransientError):
                    transient_failures.append(err.original_error)

    # With thread_pool_max_size=10 and no retries, we expect at least some TransientError failures
    assert len(transient_failures) > 0, (
        f"Expected at least one TransientError from thread pool exhaustion, but got none. Results: {results}"
    )

    expected_message = "There are no available threads to serve this request at the moment"
    for failure in transient_failures:
        assert expected_message in str(failure), f"Expected thread pool exhaustion message, got: {failure}"
