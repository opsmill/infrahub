import inspect
from pathlib import Path

import pytest

from infrahub.core import registry
from infrahub.core.validators.uniqueness.model import (
    NodeUniquenessQueryRequest,
    QueryAttributePath,
    QueryRelationshipAttributePath,
)
from infrahub.core.validators.uniqueness.query import NodeUniqueAttributeConstraintQuery
from infrahub.database import QueryConfig
from infrahub.database.constants import Neo4jRuntime
from infrahub.log import get_logger
from tests.helpers.constants import NEO4J_COMMUNITY_IMAGE, NEO4J_ENTERPRISE_IMAGE
from tests.helpers.query_benchmark.benchmark_config import BenchmarkConfig
from tests.helpers.query_benchmark.car_person_generators import (
    CarGeneratorWithOwnerHavingUniqueCar,
)
from tests.helpers.query_benchmark.data_generator import load_data_and_profile
from tests.helpers.query_benchmark.db_query_profiler import BenchmarkConfig, GraphProfileGenerator
from tests.query_benchmark.conftest import RESULTS_FOLDER
from tests.query_benchmark.utils import start_db_and_create_default_branch

log = get_logger()

# pytestmark = pytest.mark.skip("Not relevant to test this currently.")


async def benchmark_uniqueness_query(
    query_request,
    car_person_schema_root,
    graph_generator: GraphProfileGenerator,
    benchmark_config: BenchmarkConfig,
    test_params_label: str,
    test_name: str,
):
    """
    Profile NodeUniqueAttributeConstraintQuery with a given query_request / configuration, using a Car generator.
    """

    # Initialization
    queries_names_to_config = {
        NodeUniqueAttributeConstraintQuery.name: QueryConfig(neo4j_runtime=benchmark_config.neo4j_runtime)
    }
    db_profiling_queries, default_branch = await start_db_and_create_default_branch(
        neo4j_image=benchmark_config.neo4j_image,
        load_indexes=benchmark_config.load_db_indexes,
        queries_names_to_config=queries_names_to_config,
    )
    registry.schema.register_schema(schema=car_person_schema_root, branch=default_branch.name)

    # Build function to profile
    async def init_and_execute():
        # Need this function to avoid loading data between `init` and `execute` methods.
        query = await NodeUniqueAttributeConstraintQuery.init(
            db=db_profiling_queries,
            branch=default_branch,
            query_request=query_request,
        )
        await query.execute(db=db_profiling_queries)
        assert len(query.results) == 0  # supposed to have no violation with CarGeneratorWithOwnerHavingUniqueCar

    nb_cars = 10_000
    cars_generator = CarGeneratorWithOwnerHavingUniqueCar(db=db_profiling_queries, nb_persons=nb_cars)
    module_name = Path(__file__).stem
    graph_output_location = RESULTS_FOLDER / module_name / test_name

    await load_data_and_profile(
        data_generator=cars_generator,
        func_call=init_and_execute,
        profile_frequency=100,
        nb_elements=nb_cars,
        graphs_output_location=graph_output_location,
        test_label=test_params_label,
        graph_generator=graph_generator,
    )


@pytest.mark.parametrize(
    "query_request",
    [
        NodeUniquenessQueryRequest(
            kind="TestCar", unique_attribute_paths={QueryAttributePath(attribute_name="name", property_name="value")}
        ),
        NodeUniquenessQueryRequest(
            kind="TestCar",
            unique_attribute_paths={
                QueryAttributePath(attribute_name="name", property_name="value"),
                QueryAttributePath(attribute_name="nbr_seats", property_name="value"),
            },
        ),
        NodeUniquenessQueryRequest(
            kind="TestCar",
            unique_attribute_paths={
                QueryAttributePath(attribute_name="name", property_name="value"),
                QueryAttributePath(attribute_name="nbr_seats", property_name="value"),
            },
            relationship_attribute_paths={
                QueryRelationshipAttributePath(identifier="testcar__testperson", attribute_name="name")
            },
        ),
    ],
)
async def test_multiple_constraints(query_request, car_person_schema_root, graph_generator):
    benchmark_config = BenchmarkConfig(neo4j_runtime=Neo4jRuntime.DEFAULT, neo4j_image=NEO4J_ENTERPRISE_IMAGE)
    await benchmark_uniqueness_query(
        query_request=query_request,
        car_person_schema_root=car_person_schema_root,
        benchmark_config=benchmark_config,
        test_params_label=str(query_request),
        test_name=inspect.currentframe().f_code.co_name,
        graph_generator=graph_generator,
    )


@pytest.mark.parametrize(
    "benchmark_config",
    [
        BenchmarkConfig(neo4j_runtime=Neo4jRuntime.DEFAULT, neo4j_image=NEO4J_COMMUNITY_IMAGE),
        BenchmarkConfig(neo4j_runtime=Neo4jRuntime.DEFAULT, neo4j_image=NEO4J_ENTERPRISE_IMAGE),
        BenchmarkConfig(neo4j_runtime=Neo4jRuntime.PARALLEL, neo4j_image=NEO4J_ENTERPRISE_IMAGE),
    ],
)
async def test_multiple_runtimes(benchmark_config, car_person_schema_root, graph_generator):
    query_request = NodeUniquenessQueryRequest(
        kind="TestCar",
        unique_attribute_paths={
            QueryAttributePath(attribute_name="name", property_name="value"),
            QueryAttributePath(attribute_name="nbr_seats", property_name="value"),
        },
        relationship_attribute_paths={
            QueryRelationshipAttributePath(identifier="testcar__testperson", attribute_name="name")
        },
    )

    await benchmark_uniqueness_query(
        query_request=query_request,
        car_person_schema_root=car_person_schema_root,
        benchmark_config=benchmark_config,
        test_params_label=str(benchmark_config),
        test_name=inspect.currentframe().f_code.co_name,
        graph_generator=graph_generator,
    )


@pytest.mark.parametrize(
    "benchmark_config",
    [
        # BenchmarkConfig(neo4j_runtime=Neo4jRuntime.PARALLEL, neo4j_image=NEO4J_ENTERPRISE_IMAGE, load_db_indexes=False),
        BenchmarkConfig(neo4j_runtime=Neo4jRuntime.PARALLEL, neo4j_image=NEO4J_ENTERPRISE_IMAGE, load_db_indexes=True),
        # BenchmarkConfig(neo4j_runtime=Neo4jRuntime.DEFAULT, neo4j_image=NEO4J_ENTERPRISE_IMAGE, load_db_indexes=False),
        # BenchmarkConfig(neo4j_runtime=Neo4jRuntime.DEFAULT, neo4j_image=NEO4J_ENTERPRISE_IMAGE, load_db_indexes=True),
        # BenchmarkConfig(neo4j_runtime=Neo4jRuntime.DEFAULT, neo4j_image=NEO4J_COMMUNITY_IMAGE, load_db_indexes=False),
        # BenchmarkConfig(neo4j_runtime=Neo4jRuntime.DEFAULT, neo4j_image=NEO4J_COMMUNITY_IMAGE, load_db_indexes=True),
    ],
)
async def test_indexes(benchmark_config, car_person_schema_root, graph_generator):
    query_request = NodeUniquenessQueryRequest(
        kind="TestCar",
        unique_attribute_paths={
            QueryAttributePath(attribute_name="name", property_name="value"),
            QueryAttributePath(attribute_name="nbr_seats", property_name="value"),
        },
        relationship_attribute_paths={
            QueryRelationshipAttributePath(identifier="testcar__testperson", attribute_name="name")
        },
    )

    await benchmark_uniqueness_query(
        query_request=query_request,
        car_person_schema_root=car_person_schema_root,
        benchmark_config=benchmark_config,
        test_params_label=str(benchmark_config),
        test_name=inspect.currentframe().f_code.co_name,
        graph_generator=graph_generator,
    )
