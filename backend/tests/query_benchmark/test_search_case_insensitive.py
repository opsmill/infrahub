"""
Regression benchmark: case-insensitive search via toLower() vs indexed value_lower property.

Demonstrates that toLower(toString(av.value)) CONTAINS ... bypasses indexes and becomes
increasingly slow as the number of AttributeValueIndexed nodes grows, while a pre-computed
`value_lower` property on AttributeValueIndexed can leverage a TEXT index for O(1)-ish lookups.

The write path now stores `value_lower` automatically and the TEXT index is defined in
`backend/infrahub/core/graph/index.py`, so no manual backfill or index creation is needed.

Usage:
    pytest backend/tests/query_benchmark/test_search_case_insensitive.py -s --timeout=36000
"""

import inspect
import time
from pathlib import Path

import pytest

from infrahub.constants.database import Neo4jRuntime
from infrahub.core import registry
from infrahub.core.schema import SchemaRoot
from tests.helpers.constants import NEO4J_ENTERPRISE_IMAGE
from tests.helpers.query_benchmark.benchmark_config import BenchmarkConfig
from tests.helpers.query_benchmark.car_person_generators import CarGenerator
from tests.query_benchmark.conftest import RESULTS_FOLDER
from tests.query_benchmark.utils import start_db_and_create_default_branch

BATCH_SIZE = 500
NUM_BATCHES = 6  # Total: 3000 nodes


@pytest.mark.timeout(36000)
@pytest.mark.parametrize(
    "benchmark_config",
    [
        BenchmarkConfig(
            neo4j_runtime=Neo4jRuntime.PARALLEL,
            neo4j_image=NEO4J_ENTERPRISE_IMAGE,
            load_db_indexes=True,
        ),
    ],
)
async def test_search_tolower_vs_indexed_value_lower(
    benchmark_config: BenchmarkConfig,
    car_person_schema_root: SchemaRoot,
) -> None:
    """Compare toLower(toString()) search vs indexed value_lower property search.

    The write path now automatically stores `value_lower` on AttributeValueIndexed nodes,
    and the TEXT index on value_lower is defined in graph/index.py. This test verifies
    that the indexed approach is consistently faster than toLower() at scale.
    """
    db, default_branch = await start_db_and_create_default_branch(
        neo4j_image=benchmark_config.neo4j_image,
        load_indexes=benchmark_config.load_db_indexes,
    )
    registry.schema.register_schema(schema=car_person_schema_root, branch=default_branch.name)

    cars_generator = CarGenerator(db=db)

    # --- Cypher templates ------------------------------------------------------
    # Old approach: toLower(toString()) - cannot use any index
    cypher_tolower = """
    MATCH (av:AttributeValueIndexed)<-[:HAS_VALUE]-(attr:Attribute)<-[:HAS_ATTRIBUTE]-(n)
    WHERE toLower(toString(av.value)) CONTAINS toLower(toString($search_value))
    RETURN DISTINCT n.uuid AS uuid
    """

    # New approach: pre-computed value_lower property with TEXT index
    cypher_value_lower = """
    MATCH (av:AttributeValueIndexed)<-[:HAS_VALUE]-(attr:Attribute)<-[:HAS_ATTRIBUTE]-(n)
    WHERE av.value_lower CONTAINS $search_value
    RETURN DISTINCT n.uuid AS uuid
    """

    search_params_tolower = {"search_value": "car-"}  # partial match present in every car name
    search_params_indexed = {"search_value": "car-"}  # already lowercase

    timings_tolower: list[tuple[int, float]] = []
    timings_indexed: list[tuple[int, float]] = []

    total_nodes = 0

    for batch_idx in range(NUM_BATCHES):
        # Load more data — value_lower is set automatically by the write path
        await cars_generator.load_data(nb_elements=BATCH_SIZE)
        total_nodes += BATCH_SIZE

        # Ensure index is up-to-date
        await db.execute_query(query="CALL db.awaitIndexes(300)", name="await_indexes")

        # Warm up both queries (avoid cold-cache bias)
        await db.execute_query(query=cypher_tolower, params=search_params_tolower, name="warmup_tolower")
        await db.execute_query(query=cypher_value_lower, params=search_params_indexed, name="warmup_indexed")

        # --- Measure toLower approach ---
        runs_tolower = []
        for _ in range(3):
            t0 = time.perf_counter()
            await db.execute_query(query=cypher_tolower, params=search_params_tolower, name="search_tolower")
            runs_tolower.append(time.perf_counter() - t0)
        avg_tolower = sum(runs_tolower) / len(runs_tolower)
        timings_tolower.append((total_nodes, avg_tolower))

        # --- Measure value_lower indexed approach ---
        runs_indexed = []
        for _ in range(3):
            t0 = time.perf_counter()
            await db.execute_query(query=cypher_value_lower, params=search_params_indexed, name="search_value_lower")
            runs_indexed.append(time.perf_counter() - t0)
        avg_indexed = sum(runs_indexed) / len(runs_indexed)
        timings_indexed.append((total_nodes, avg_indexed))

        print(
            f"[batch {batch_idx + 1}/{NUM_BATCHES}] nodes={total_nodes:>5}  "
            f"toLower={avg_tolower * 1000:.1f}ms  "
            f"value_lower={avg_indexed * 1000:.1f}ms  "
            f"speedup={avg_tolower / avg_indexed:.1f}x"
        )

    # --- Write results to file for later analysis ------------------------------
    test_name = inspect.currentframe().f_code.co_name
    module_name = Path(__file__).stem
    output_dir = RESULTS_FOLDER / module_name / test_name
    output_dir.mkdir(parents=True, exist_ok=True)

    lines = ["total_nodes,tolower_ms,value_lower_ms,speedup"]
    for (n1, t1), (_, t2) in zip(timings_tolower, timings_indexed, strict=True):
        speedup = t1 / t2 if t2 > 0 else float("inf")
        lines.append(f"{n1},{t1 * 1000:.2f},{t2 * 1000:.2f},{speedup:.2f}")
    (output_dir / "results.csv").write_text("\n".join(lines) + "\n", encoding="utf-8")

    # --- Regression assertion --------------------------------------------------
    # At the largest data size, the indexed approach should be meaningfully faster.
    # We use a conservative threshold: indexed must be at least 1.5x faster at scale.
    final_tolower = timings_tolower[-1][1]
    final_indexed = timings_indexed[-1][1]
    final_speedup = final_tolower / final_indexed if final_indexed > 0 else float("inf")

    print(f"\nFinal comparison at {timings_tolower[-1][0]} nodes:")
    print(f"  toLower:     {final_tolower * 1000:.1f}ms")
    print(f"  value_lower: {final_indexed * 1000:.1f}ms")
    print(f"  speedup:     {final_speedup:.1f}x")

    min_expected_speedup = 1.5
    assert final_speedup > min_expected_speedup, (
        f"Expected indexed value_lower to be at least {min_expected_speedup}x faster than toLower() "
        f"at {timings_tolower[-1][0]} nodes, "
        f"but speedup was only {final_speedup:.1f}x "
        f"(toLower={final_tolower * 1000:.1f}ms, value_lower={final_indexed * 1000:.1f}ms)"
    )
