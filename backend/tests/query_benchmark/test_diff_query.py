import inspect
from pathlib import Path

import pytest

from infrahub.core import registry
from infrahub.core.initialization import create_branch
from infrahub.core.query.diff import DiffAllPathsQuery
from infrahub.core.timestamp import Timestamp
from infrahub.database.constants import Neo4jRuntime
from infrahub.log import get_logger
from tests.helpers.constants import NEO4J_ENTERPRISE_IMAGE
from tests.helpers.query_benchmark.benchmark_config import BenchmarkConfig
from tests.helpers.query_benchmark.car_person_generators import (
    CarWithDiffInSecondBranchGenerator,
)
from tests.helpers.query_benchmark.data_generator import load_data_and_profile
from tests.query_benchmark.conftest import RESULTS_FOLDER
from tests.query_benchmark.utils import start_db_and_create_default_branch

log = get_logger()

# pytestmark = pytest.mark.skip("Not relevant to test this currently.")


@pytest.mark.parametrize(
    "benchmark_config",
    [
        # BenchmarkConfig(neo4j_runtime=Neo4jRuntime.DEFAULT, neo4j_image=NEO4J_COMMUNITY_IMAGE),
        # BenchmarkConfig(neo4j_runtime=Neo4jRuntime.DEFAULT, neo4j_image=NEO4J_ENTERPRISE_IMAGE),
        BenchmarkConfig(neo4j_runtime=Neo4jRuntime.PARALLEL, neo4j_image=NEO4J_ENTERPRISE_IMAGE),
    ],
)
async def test_diff(benchmark_config, car_person_schema_root, graph_generator):

    # Initialization
    db_profiling_queries, default_branch = await start_db_and_create_default_branch(
        neo4j_image=benchmark_config.neo4j_image,
        load_indexes=benchmark_config.load_db_indexes,
    )
    registry.schema.register_schema(schema=car_person_schema_root, branch=default_branch.name)
    diff_branch = await create_branch(branch_name="diff_branch", db=db_profiling_queries)

    # Build function to profile
    async def init_and_execute():
        # Need this function to avoid loading data between `init` and `execute` methods.
        query = await DiffAllPathsQuery.init(
            db=db_profiling_queries,
            branch=diff_branch,
            base_branch=default_branch,
            diff_branch_from_time=Timestamp(default_branch.branched_from),
            diff_from=Timestamp(default_branch.branched_from),
            diff_to=Timestamp(),
        )
        await query.execute(db=db_profiling_queries)
        print(f"{query.results=}")

    nb_cars = 2
    cars_generator = CarWithDiffInSecondBranchGenerator(
        db=db_profiling_queries, nb_persons=2, diff_ratio=0.2, main_branch=default_branch, diff_branch=diff_branch
    )

    test_name = inspect.currentframe().f_code.co_name
    module_name = Path(__file__).stem
    graph_output_location = RESULTS_FOLDER / module_name / test_name

    test_label = str(benchmark_config)

    await load_data_and_profile(
        data_generator=cars_generator,
        func_call=init_and_execute,
        profile_frequency=5,
        nb_elements=nb_cars,
        graphs_output_location=graph_output_location,
        test_label=test_label,
        graph_generator=graph_generator,
    )
