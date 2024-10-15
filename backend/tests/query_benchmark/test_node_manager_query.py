import inspect
from functools import partial
from pathlib import Path

import pytest

from infrahub.core import registry
from infrahub.core.manager import NodeManager
from infrahub.core.query.node import NodeGetListQuery, NodeListGetAttributeQuery, NodeListGetInfoQuery
from infrahub.database import QueryConfig
from infrahub.database.constants import Neo4jRuntime
from infrahub.log import get_logger
from tests.helpers.constants import NEO4J_COMMUNITY_IMAGE, NEO4J_ENTERPRISE_IMAGE
from tests.helpers.query_benchmark.car_person_generators import (
    CarGenerator,
    PersonFromExistingCarGenerator,
    PersonGenerator,
)
from tests.helpers.query_benchmark.data_generator import load_data_and_profile
from tests.query_benchmark.utils import start_db_and_create_default_branch

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
async def test_query_persons(query_analyzer, neo4j_image: str, neo4j_runtime: Neo4jRuntime, car_person_schema_root):
    queries_names_to_config = {
        NodeGetListQuery.name: QueryConfig(neo4j_runtime=neo4j_runtime),
        NodeListGetAttributeQuery.name: QueryConfig(neo4j_runtime=neo4j_runtime),
        NodeListGetInfoQuery.name: QueryConfig(neo4j_runtime=neo4j_runtime),
    }
    db_profiling_queries, default_branch = await start_db_and_create_default_branch(
        neo4j_image=neo4j_image, queries_names_to_config=queries_names_to_config, query_analyzer=query_analyzer
    )

    registry.schema.register_schema(schema=car_person_schema_root, branch=default_branch.name)
    person_schema = registry.schema.get_node_schema(name="TestPerson", branch=default_branch)
    func_call = partial(NodeManager.query, db=db_profiling_queries, limit=50, schema=person_schema)

    person_generator = PersonGenerator(db=db_profiling_queries)

    graph_output_location = RESULTS_FOLDER / inspect.currentframe().f_code.co_name

    await load_data_and_profile(
        data_generator=person_generator,
        func_call=func_call,
        profile_frequency=50,
        nb_elements=1000,
        graphs_output_location=graph_output_location,
        query_analyzer=query_analyzer,
        test_label=f" data: {neo4j_image}" + f" runtime: {neo4j_runtime}",
    )


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
async def test_query_persons_with_isolated_cars(
    query_analyzer, neo4j_image: str, neo4j_runtime: Neo4jRuntime, car_person_schema_root
):
    queries_names_to_config = {
        NodeGetListQuery.name: QueryConfig(neo4j_runtime=neo4j_runtime),
        NodeListGetAttributeQuery.name: QueryConfig(neo4j_runtime=neo4j_runtime),
        NodeListGetInfoQuery.name: QueryConfig(neo4j_runtime=neo4j_runtime),
    }
    db_profiling_queries, default_branch = await start_db_and_create_default_branch(
        neo4j_image=neo4j_image, queries_names_to_config=queries_names_to_config, query_analyzer=query_analyzer
    )

    registry.schema.register_schema(schema=car_person_schema_root, branch=default_branch.name)
    person_schema = registry.schema.get_node_schema(name="TestPerson", branch=default_branch)
    func_call = partial(NodeManager.query, db=db_profiling_queries, limit=50, schema=person_schema)

    graph_output_location = RESULTS_FOLDER / inspect.currentframe().f_code.co_name

    # Load cars in database, that are not connected to persons being queried.
    cars_generator = CarGenerator(db=db_profiling_queries)
    await cars_generator.load_cars(nb_cars=1000)

    person_generator = PersonGenerator(db=db_profiling_queries)

    # Load persons, and run/profile NodeManager.query at a given frequency
    await load_data_and_profile(
        data_generator=person_generator,
        func_call=func_call,
        profile_frequency=50,
        nb_elements=1000,
        graphs_output_location=graph_output_location,
        query_analyzer=query_analyzer,
        test_label=f" data: {neo4j_image}" + f" runtime: {neo4j_runtime}",
    )


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
async def test_query_persons_with_connected_cars(
    query_analyzer, neo4j_image: str, neo4j_runtime: Neo4jRuntime, car_person_schema_root
):
    queries_names_to_config = {
        NodeGetListQuery.name: QueryConfig(neo4j_runtime=neo4j_runtime),
        NodeListGetAttributeQuery.name: QueryConfig(neo4j_runtime=neo4j_runtime),
        NodeListGetInfoQuery.name: QueryConfig(neo4j_runtime=neo4j_runtime),
    }
    db_profiling_queries, default_branch = await start_db_and_create_default_branch(
        neo4j_image=neo4j_image, queries_names_to_config=queries_names_to_config, query_analyzer=query_analyzer
    )

    registry.schema.register_schema(schema=car_person_schema_root, branch=default_branch.name)
    person_schema = registry.schema.get_node_schema(name="TestPerson", branch=default_branch)
    func_call = partial(NodeManager.query, db=db_profiling_queries, limit=50, schema=person_schema)

    graph_output_location = RESULTS_FOLDER / inspect.currentframe().f_code.co_name

    person_generator = PersonFromExistingCarGenerator(db=db_profiling_queries, nb_cars=1000)

    # Load persons, and run/profile NodeManager.query at a given frequency
    await load_data_and_profile(
        data_generator=person_generator,
        func_call=func_call,
        profile_frequency=50,
        nb_elements=1000,
        graphs_output_location=graph_output_location,
        query_analyzer=query_analyzer,
        test_label=f" data: {neo4j_image}" + f" runtime: {neo4j_runtime}",
    )
