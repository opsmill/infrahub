import inspect
from pathlib import Path

import pytest

from infrahub.constants.database import Neo4jRuntime
from infrahub.core import registry
from infrahub.core.query.node import NodeGetListQuery
from infrahub.core.schema import SchemaRoot
from infrahub.log import get_logger
from tests.helpers.constants import NEO4J_ENTERPRISE_IMAGE
from tests.helpers.query_benchmark.benchmark_config import BenchmarkConfig
from tests.helpers.query_benchmark.car_person_generators import (
    CarGenerator,
)
from tests.helpers.query_benchmark.data_generator import load_data_and_profile
from tests.helpers.query_benchmark.db_query_profiler import GraphProfileGenerator
from tests.query_benchmark.conftest import RESULTS_FOLDER
from tests.query_benchmark.utils import start_db_and_create_default_branch

log = get_logger()


@pytest.mark.timeout(36000)  # 10 hours
@pytest.mark.parametrize(
    "benchmark_config, ordering",
    [
        (
            BenchmarkConfig(
                neo4j_runtime=Neo4jRuntime.PARALLEL, neo4j_image=NEO4J_ENTERPRISE_IMAGE, load_db_indexes=False
            ),
            False,
        ),
        (
            BenchmarkConfig(
                neo4j_runtime=Neo4jRuntime.PARALLEL, neo4j_image=NEO4J_ENTERPRISE_IMAGE, load_db_indexes=False
            ),
            True,
        ),
    ],
)
async def test_node_get_list_ordering(
    benchmark_config: BenchmarkConfig,
    car_person_schema_root: SchemaRoot,
    graph_generator: GraphProfileGenerator,
    increase_query_size_limit: None,
    ordering: bool,
) -> None:
    # Initialization
    db_profiling_queries, default_branch = await start_db_and_create_default_branch(
        neo4j_image=benchmark_config.neo4j_image,
        load_indexes=benchmark_config.load_db_indexes,
    )
    registry.schema.register_schema(schema=car_person_schema_root, branch=default_branch.name)

    # Build function to profile
    async def init_and_execute():
        car_node_schema = registry.get_node_schema(name="TestCar", branch=default_branch.name)
        query = await NodeGetListQuery.init(
            db=db_profiling_queries,
            schema=car_node_schema,
            branch=default_branch,
            ordering=ordering,
        )
        res = await query.execute(db=db_profiling_queries)
        return res

    nb_cars = 10_000
    cars_generator = CarGenerator(db=db_profiling_queries)
    test_name = inspect.currentframe().f_code.co_name
    module_name = Path(__file__).stem
    graph_output_location = RESULTS_FOLDER / module_name / test_name

    test_label = str(benchmark_config) + "_ordering_" + str(ordering)

    await load_data_and_profile(
        data_generator=cars_generator,
        func_call=init_and_execute,
        profile_frequency=1_000,
        nb_elements=nb_cars,
        graphs_output_location=graph_output_location,
        test_label=test_label,
        graph_generator=graph_generator,
    )
