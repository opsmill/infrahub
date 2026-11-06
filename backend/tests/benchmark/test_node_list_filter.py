"""Benchmark list reads that filter by an attribute value, on the default branch, on a branch and branch-agnostic.

Run it once per code version and compare the runs:
  INFRAHUB_LOG_LEVEL=CRITICAL uv run pytest backend/tests/benchmark/test_node_list_filter.py \
      --dist=no --benchmark-group-by=name --benchmark-autosave --benchmark-compare

`INFRAHUB_BENCHMARK_NBR_CARS` sets the number of cars. Each run also saves the database hits Neo4j reports for the
query under `extra_info`, which does not depend on the speed of the machine.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import pytest

from infrahub.core import registry
from infrahub.core.initialization import (
    create_branch,
    create_default_branch,
    create_global_branch,
    create_root_node,
)
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.query.node import NodeGetListQuery
from infrahub.core.schema import SchemaRoot, core_models, internal_schema
from infrahub.core.schema.manager import SchemaManager
from infrahub.core.utils import delete_all_nodes
from tests.constants import TestKind
from tests.helpers.schema import CAR_SCHEMA, load_schema

if TYPE_CHECKING:
    from collections.abc import Callable

    from pytest_benchmark.fixture import BenchmarkFixture

    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase

NBR_WARMUP = int(os.getenv("INFRAHUB_BENCHMARK_NBR_WARMUP", "5"))
NBR_CARS = int(os.getenv("INFRAHUB_BENCHMARK_NBR_CARS", "2000"))
NBR_PERSONS = max(NBR_CARS // 10, 1)
COLORS = ["red", "blue", "green", "black", "white", "silver", "yellow", "orange", "purple", "brown"]


@dataclass
class FilterDataset:
    default_branch: Branch
    branch: Branch
    ids: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True, kw_only=True)
class FilterBenchmarkCase:
    name: str
    filters: dict[str, Any]
    on_branch: bool = False
    branch_agnostic: bool = False


FILTER_BENCHMARK_CASES = [
    FilterBenchmarkCase(name="attribute_value_on_default", filters={"color__value": "red"}),
    FilterBenchmarkCase(name="attribute_value_on_branch", filters={"color__value": "red"}, on_branch=True),
    FilterBenchmarkCase(name="attribute_value_branch_agnostic", filters={"color__value": "red"}, branch_agnostic=True),
    FilterBenchmarkCase(name="peer_attribute_value_on_default", filters={"owner__name__value": "person-7"}),
    FilterBenchmarkCase(
        name="peer_attribute_value_on_branch", filters={"owner__name__value": "person-7"}, on_branch=True
    ),
]


async def _update(db: InfrahubDatabase, branch: Branch, node_id: str, **attributes: Any) -> None:
    node = await NodeManager.get_one(db=db, id=node_id, branch=branch, raise_on_error=True)
    for attribute_name, value in attributes.items():
        getattr(node, attribute_name).value = value
    await node.save(db=db)


@pytest.fixture(scope="module")
async def dataset(db: InfrahubDatabase) -> FilterDataset:
    registry.delete_all()
    await delete_all_nodes(db=db)
    await create_root_node(db=db)
    default_branch = await create_default_branch(db=db)
    await create_global_branch(db=db)
    registry.schema = SchemaManager()
    schema_branch = registry.schema.get_schema_branch(name=default_branch.name)
    schema_branch.load_schema(schema=SchemaRoot(**internal_schema))
    schema_branch.load_schema(schema=SchemaRoot(**core_models))
    schema_branch.process()
    default_branch.update_schema_hash()
    await default_branch.save(db=db)
    await load_schema(db=db, schema=CAR_SCHEMA)

    dataset = FilterDataset(default_branch=default_branch, branch=default_branch)
    maker = await Node.init(db=db, schema=TestKind.MANUFACTURER)
    await maker.new(db=db, name="maker")
    await maker.save(db=db)
    for idx in range(NBR_PERSONS):
        person = await Node.init(db=db, schema=TestKind.PERSON)
        await person.new(db=db, name=f"person-{idx}")
        await person.save(db=db)
        dataset.ids[f"person-{idx}"] = person.id
    for idx in range(NBR_CARS):
        car = await Node.init(db=db, schema=TestKind.CAR)
        await car.new(
            db=db,
            name=f"car-{idx}",
            color=COLORS[idx % len(COLORS)],
            manufacturer=maker,
            owner=dataset.ids[f"person-{idx % NBR_PERSONS}"],
        )
        await car.save(db=db)
        dataset.ids[f"car-{idx}"] = car.id

    dataset.branch = await create_branch(db=db, branch_name="benchmark-filters")
    for idx in range(0, NBR_CARS, 2 * len(COLORS)):
        await _update(db, dataset.branch, dataset.ids[f"car-{idx}"], color="blue")
        await _update(db, default_branch, dataset.ids[f"car-{idx + 1}"], color="red")
    for idx in range(0, NBR_PERSONS, len(COLORS)):
        await _update(db, dataset.branch, dataset.ids[f"person-{idx}"], name=f"renamed-{idx}")

    return dataset


async def _count_db_hits(db: InfrahubDatabase, query: NodeGetListQuery) -> int:
    rendered = query.render()
    response = await db.run_query(query="PROFILE " + rendered.text, params=rendered.params, name="benchmark")
    summary = await response.consume()

    def _sum(plan: dict[str, Any]) -> int:
        return int(plan.get("dbHits", 0)) + sum(_sum(child) for child in plan.get("children", []))

    return _sum(summary.profile or {})


@pytest.mark.parametrize("case", FILTER_BENCHMARK_CASES, ids=lambda case: case.name)
def test_node_list_filter(
    exec_async: Callable[..., Any],
    aio_benchmark: Callable[..., Any],
    benchmark: BenchmarkFixture,
    db: InfrahubDatabase,
    dataset: FilterDataset,
    case: FilterBenchmarkCase,
) -> None:
    branch = dataset.branch if case.on_branch else dataset.default_branch
    car_schema = registry.schema.get_node_schema(name=TestKind.CAR, branch=branch)

    async def list_cars() -> NodeGetListQuery:
        query = await NodeGetListQuery.init(
            db=db, branch=branch, schema=car_schema, filters=case.filters, branch_agnostic=case.branch_agnostic
        )
        await query.execute(db=db)
        return query

    query = exec_async(list_cars)
    for _ in range(NBR_WARMUP):
        exec_async(list_cars)

    benchmark.extra_info["db_hits"] = exec_async(_count_db_hits, db=db, query=query)
    benchmark.extra_info["rows"] = len(query.get_node_ids())
    aio_benchmark(list_cars)
