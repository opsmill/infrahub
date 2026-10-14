import inspect
import uuid
from pathlib import Path

import pytest

from infrahub.constants.database import Neo4jRuntime
from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.branch.enums import BranchStatus
from infrahub.core.constants import GLOBAL_BRANCH_NAME
from infrahub.core.query.repository import RepositoryBranchAttributesQuery
from infrahub.core.schema import SchemaRoot
from infrahub.core.timestamp import Timestamp
from infrahub.log import get_logger
from tests.helpers.constants import NEO4J_ENTERPRISE_IMAGE
from tests.helpers.query_benchmark.benchmark_config import BenchmarkConfig
from tests.helpers.query_benchmark.car_person_generators import CarGenerator
from tests.helpers.query_benchmark.data_generator import DataGenerator, load_data_and_profile
from tests.helpers.query_benchmark.db_query_profiler import GraphProfileGenerator, InfrahubDatabaseProfiler
from tests.query_benchmark.conftest import RESULTS_FOLDER
from tests.query_benchmark.utils import start_db_and_create_default_branch

log = get_logger()

ATTRIBUTE_NAMES = ["name", "nbr_seats"]
NB_NODES = 2
NB_BRANCHES = 200
PROFILE_FREQUENCY = 5


class BranchGenerator(DataGenerator):
    """Save open, isolated branches, the dimension this read's cost scales on.

    No schema branch is registered for them: the statement under profile reads `Branch` nodes and
    the attribute edges directly, so the branches only have to exist in the graph.
    """

    def __init__(self, db: InfrahubDatabaseProfiler) -> None:
        super().__init__(db=db)
        self.branch_names: list[str] = []

    async def load_data(self, nb_elements: int) -> None:
        for _ in range(nb_elements):
            name = f"benchmark-branch-{uuid.uuid4().hex[:12]}"
            branch = Branch(
                name=name,
                status=BranchStatus.OPEN,
                description=f"branch {name}",
                is_default=False,
                sync_with_git=True,
                is_isolated=True,
                branched_from=Timestamp().to_string(),
            )
            await branch.save(db=self.db)
            self.branch_names.append(name)


@pytest.mark.timeout(36000)  # 10 hours
@pytest.mark.parametrize(
    "benchmark_config",
    [
        BenchmarkConfig(neo4j_runtime=Neo4jRuntime.DEFAULT, neo4j_image=NEO4J_ENTERPRISE_IMAGE, load_db_indexes=False),
        BenchmarkConfig(neo4j_runtime=Neo4jRuntime.DEFAULT, neo4j_image=NEO4J_ENTERPRISE_IMAGE, load_db_indexes=True),
    ],
)
async def test_repository_branch_attributes(
    benchmark_config: BenchmarkConfig,
    car_person_schema_root: SchemaRoot,
    graph_generator: GraphProfileGenerator,
    increase_query_size_limit: None,
) -> None:
    """Profile the cross-branch attribute read as the branch set grows from one page to two hundred.

    The two configurations differ only in whether the database indexes are loaded, so the pair also
    tracks what the range index on the branch name is worth to the opening `UNWIND ... MATCH`.
    """
    db_profiling_queries, default_branch = await start_db_and_create_default_branch(
        neo4j_image=benchmark_config.neo4j_image,
        load_indexes=benchmark_config.load_db_indexes,
    )
    registry.schema.register_schema(schema=car_person_schema_root, branch=default_branch.name)

    # The statement selects nodes by uuid and attributes by name, never by kind, so any branch-aware
    # kind with the requested attributes profiles the same traversal.
    nodes = await CarGenerator(db=db_profiling_queries).load_cars(branch=default_branch, nb_cars=NB_NODES)
    node_ids = [node.id for node in nodes.values()]

    branch_generator = BranchGenerator(db=db_profiling_queries)

    async def init_and_execute() -> None:
        # Need this function to avoid loading data between `init` and `execute` methods.
        query = await RepositoryBranchAttributesQuery.init(
            db=db_profiling_queries,
            repository_ids=node_ids,
            branch_names=list(branch_generator.branch_names),
            attribute_names=ATTRIBUTE_NAMES,
            default_branch_name=default_branch.name,
            global_branch_name=GLOBAL_BRANCH_NAME,
        )
        await query.execute(db=db_profiling_queries)
        assert len(query.results) == len(node_ids) * len(branch_generator.branch_names) * len(ATTRIBUTE_NAMES)

    test_name = inspect.currentframe().f_code.co_name
    module_name = Path(__file__).stem
    graph_output_location = RESULTS_FOLDER / module_name / test_name

    await load_data_and_profile(
        data_generator=branch_generator,
        func_call=init_and_execute,
        profile_frequency=PROFILE_FREQUENCY,
        nb_elements=NB_BRANCHES,
        graphs_output_location=graph_output_location,
        test_label=str(benchmark_config),
        graph_generator=graph_generator,
    )
