import inspect
from functools import partial
from pathlib import Path

import pytest

from infrahub.core import registry
from infrahub.core.validators.uniqueness.model import NodeUniquenessQueryRequest, QueryAttributePath
from infrahub.core.validators.uniqueness.query import NodeUniqueAttributeConstraintQuery
from infrahub.database import QueryConfig
from infrahub.database.constants import Neo4jRuntime
from infrahub.log import get_logger
from tests.helpers.constants import NEO4J_COMMUNITY_IMAGE, NEO4J_ENTERPRISE_IMAGE
from tests.helpers.query_benchmark.car_person_generators import (
    CarGenerator,
)
from tests.helpers.query_benchmark.data_generator import load_data_and_profile

from .utils import start_db_and_create_default_branch

RESULTS_FOLDER = Path(__file__).resolve().parent / "query_performance_results"

log = get_logger()


@pytest.mark.parametrize(
    "neo4j_image, neo4j_runtime",
    [
        (
            NEO4J_ENTERPRISE_IMAGE,
            Neo4jRuntime.PARALLEL,
        ),
        (
            NEO4J_ENTERPRISE_IMAGE,
            Neo4jRuntime.DEFAULT,
        ),
        (
            NEO4J_COMMUNITY_IMAGE,
            Neo4jRuntime.DEFAULT,
        ),
    ],
)
async def test_query_unique_cars_single_attribute(
    query_analyzer, neo4j_image: str, neo4j_runtime: Neo4jRuntime, car_person_schema_root
):
    queries_names_to_config = {NodeUniqueAttributeConstraintQuery.name: QueryConfig(neo4j_runtime=neo4j_runtime)}
    db_profiling_queries, default_branch = await start_db_and_create_default_branch(
        neo4j_image=neo4j_image, queries_names_to_config=queries_names_to_config, query_analyzer=query_analyzer
    )

    # Register schema
    registry.schema.register_schema(schema=car_person_schema_root, branch=default_branch.name)

    query_unique_cars_name = await NodeUniqueAttributeConstraintQuery.init(
        db=db_profiling_queries,
        branch=default_branch,
        query_request=NodeUniquenessQueryRequest(
            kind="TestCar", unique_attribute_paths={QueryAttributePath(attribute_name="name", property_name="value")}
        ),
    )

    cars_generator = CarGenerator(db=db_profiling_queries)

    graph_output_location = RESULTS_FOLDER / inspect.currentframe().f_code.co_name

    await load_data_and_profile(
        data_generator=cars_generator,
        func_call=partial(query_unique_cars_name.execute, db=db_profiling_queries),
        profile_frequency=50,
        nb_elements=1000,
        graphs_output_location=graph_output_location,
        query_analyzer=query_analyzer,
        test_label=f" data: {neo4j_image}" + f" runtime: {neo4j_runtime}",
    )
