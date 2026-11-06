"""Benchmark the read an IP prefix pool and an IP address pool run to find their next free value.

Two datasets, each built for both pools:
- `branches`: 50 live branches and more than 1,000 past allocations: values created on the default branch before
  and after the branches, values deleted on the default branch after the branches were created, and one value
  created on each branch;
- `churn`: one live branch created first, then 300 values still allocated and 2,000 values created and deleted on the
  default branch.

Run it once per code version and compare the runs:
  INFRAHUB_LOG_LEVEL=CRITICAL uv run pytest backend/tests/benchmark/test_ip_pool_allocation.py \
      --dist=no --benchmark-group-by=name --benchmark-json=ip_pool_allocation.json

A lookup loads the pool, then asks it for its next free value. Each run saves under `extra_info` the database hits
Neo4j reports for every read query of one lookup, summed and per query name, which does not depend on the speed of the
machine.
"""

from __future__ import annotations

import ipaddress
import os
from collections import Counter
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import pytest

from infrahub.core import registry
from infrahub.core.constants import BranchSupportType, InfrahubKind
from infrahub.core.initialization import (
    create_branch,
    create_default_branch,
    create_global_branch,
    create_ipam_namespace,
    create_root_node,
)
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.node.resource_manager.ip_address_pool import CoreIPAddressPool
from infrahub.core.node.resource_manager.ip_prefix_pool import CoreIPPrefixPool
from infrahub.core.query import QueryType
from infrahub.core.schema import SchemaRoot, core_models, internal_schema
from infrahub.core.schema.manager import SchemaManager
from infrahub.core.utils import delete_all_nodes
from tests.helpers.db_query_counter import CountingInfrahubDatabase
from tests.helpers.schema import load_schema

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from neo4j import Record
    from pytest_benchmark.fixture import BenchmarkFixture

    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase

NBR_WARMUP = int(os.getenv("INFRAHUB_BENCHMARK_NBR_WARMUP", "5"))
NBR_BRANCHES = int(os.getenv("INFRAHUB_BENCHMARK_NBR_BRANCHES", "50"))
NBR_ALLOCATIONS = int(os.getenv("INFRAHUB_BENCHMARK_NBR_ALLOCATIONS", "1000"))
DELETED_EVERY = 10
"""Every tenth value created before the branches is deleted on the default branch after them."""
NBR_CHURN_ALLOCATED = int(os.getenv("INFRAHUB_BENCHMARK_NBR_CHURN_ALLOCATED", "300"))
NBR_CHURN_DELETED = int(os.getenv("INFRAHUB_BENCHMARK_NBR_CHURN_DELETED", "2000"))

PREFIX_RESOURCE = ipaddress.ip_network("10.0.0.0/8")
ALLOCATED_PREFIX_LENGTH = 24
ADDRESS_RESOURCE = ipaddress.ip_network("172.16.0.0/16")
BRANCH_PREFIX_RESOURCE = ipaddress.ip_network("10.200.0.0/16")
"""The branches allocate prefixes from here, away from the values of the default branch."""
BRANCH_ADDRESS_RESOURCE = ipaddress.ip_network("172.16.200.0/24")

IPAM_SCHEMA = SchemaRoot(
    nodes=[
        {
            "name": "IPPrefix",
            "namespace": "Ipam",
            "default_filter": "prefix__value",
            "order_by": ["prefix__value"],
            "display_label": "prefix__value",
            "branch": BranchSupportType.AWARE.value,
            "inherit_from": [InfrahubKind.IPPREFIX, InfrahubKind.WEIGHTED_POOL_RESOURCE],
        },
        {
            "name": "IPAddress",
            "namespace": "Ipam",
            "default_filter": "address__value",
            "order_by": ["address__value"],
            "display_label": "address__value",
            "branch": BranchSupportType.AWARE.value,
            "inherit_from": [InfrahubKind.IPADDRESS],
        },
    ],
)


class ProfilingInfrahubDatabase(CountingInfrahubDatabase):
    """Database that runs every read query a second time under `PROFILE` and sums the database hits by query name."""

    def __init__(self, db_hits: Counter[str] | None = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        # shared by reference so hits recorded by derived session/transaction instances land here
        self.db_hits: Counter[str] = db_hits if db_hits is not None else Counter()

    def get_context(self) -> dict[str, Any]:
        ctx = super().get_context()
        ctx["db_hits"] = self.db_hits
        return ctx

    async def execute_query_with_metadata(
        self,
        query: str,
        params: dict[str, Any] | None = None,
        name: str = "undefined",
        context: dict[str, str] | None = None,
        type: QueryType | None = None,
        timeout_seconds: float | None = None,
    ) -> tuple[list[Record], dict[str, Any]]:
        results, metadata = await super().execute_query_with_metadata(
            query=query, params=params, name=name, context=context, type=type, timeout_seconds=timeout_seconds
        )
        if type == QueryType.READ:
            response = await self.run_query(query="PROFILE " + query, params=params, name=name)
            summary = await response.consume()
            self.db_hits[name] += _sum_db_hits(summary.profile or {})
        return results, metadata


def _sum_db_hits(plan: dict[str, Any]) -> int:
    return int(plan.get("dbHits", 0)) + sum(_sum_db_hits(child) for child in plan.get("children", []))


@dataclass
class PoolDataset:
    default_branch: Branch
    branches: list[Branch] = field(default_factory=list)
    pool_ids: dict[str, str] = field(default_factory=dict)
    allocations: Counter[str] = field(default_factory=Counter)


@dataclass(frozen=True, kw_only=True)
class PoolBenchmarkCase:
    name: str
    pool_kind: str
    on_branch: bool = False


POOL_BENCHMARK_CASES = [
    PoolBenchmarkCase(name="prefix_pool_on_default", pool_kind=InfrahubKind.IPPREFIXPOOL),
    PoolBenchmarkCase(name="prefix_pool_on_branch", pool_kind=InfrahubKind.IPPREFIXPOOL, on_branch=True),
    PoolBenchmarkCase(name="address_pool_on_default", pool_kind=InfrahubKind.IPADDRESSPOOL),
    PoolBenchmarkCase(name="address_pool_on_branch", pool_kind=InfrahubKind.IPADDRESSPOOL, on_branch=True),
]


async def _create(db: InfrahubDatabase, branch: Branch, kind: str, **data: Any) -> Node:
    node = await Node.init(db=db, schema=kind, branch=branch)
    await node.new(db=db, **data)
    await node.save(db=db)
    return node


def _allocated_prefix(index: int) -> str:
    block_size = 1 << (PREFIX_RESOURCE.max_prefixlen - ALLOCATED_PREFIX_LENGTH)
    return str(
        ipaddress.ip_network((int(PREFIX_RESOURCE.network_address) + index * block_size, ALLOCATED_PREFIX_LENGTH))
    )


def _allocated_address(index: int) -> str:
    return f"{ADDRESS_RESOURCE.network_address + index + 1}/{ADDRESS_RESOURCE.prefixlen}"


async def _allocate_on_default(
    db: InfrahubDatabase, dataset: PoolDataset, namespace: Node, indexes: range
) -> tuple[list[Node], list[Node]]:
    prefixes = []
    addresses = []
    for index in indexes:
        prefixes.append(
            await _create(
                db, dataset.default_branch, "IpamIPPrefix", prefix=_allocated_prefix(index), ip_namespace=namespace
            )
        )
        addresses.append(
            await _create(
                db, dataset.default_branch, "IpamIPAddress", address=_allocated_address(index), ip_namespace=namespace
            )
        )
    dataset.allocations["prefix"] += len(indexes)
    dataset.allocations["address"] += len(indexes)
    return prefixes, addresses


async def _build_branches_dataset(db: InfrahubDatabase, dataset: PoolDataset, namespace: Node) -> None:
    half = NBR_ALLOCATIONS // 2
    before_prefixes, before_addresses = await _allocate_on_default(db, dataset, namespace, range(half))
    for index in range(NBR_BRANCHES):
        dataset.branches.append(await create_branch(db=db, branch_name=f"benchmark-{index:02d}"))
    await _allocate_on_default(db, dataset, namespace, range(half, NBR_ALLOCATIONS))
    for node in before_prefixes[::DELETED_EVERY] + before_addresses[::DELETED_EVERY]:
        await node.delete(db=db)

    branch_prefixes = list(BRANCH_PREFIX_RESOURCE.subnets(new_prefix=ALLOCATED_PREFIX_LENGTH))
    for index, branch in enumerate(dataset.branches):
        branch_namespace = await NodeManager.get_one(db=db, id=namespace.id, branch=branch, raise_on_error=True)
        await _create(db, branch, "IpamIPPrefix", prefix=str(branch_prefixes[index]), ip_namespace=branch_namespace)
        address = f"{BRANCH_ADDRESS_RESOURCE.network_address + index + 1}/{ADDRESS_RESOURCE.prefixlen}"
        await _create(db, branch, "IpamIPAddress", address=address, ip_namespace=branch_namespace)
    dataset.allocations["prefix"] += NBR_BRANCHES
    dataset.allocations["address"] += NBR_BRANCHES


async def _build_churn_dataset(db: InfrahubDatabase, dataset: PoolDataset, namespace: Node) -> None:
    dataset.branches.append(await create_branch(db=db, branch_name="benchmark-old"))
    await _allocate_on_default(db, dataset, namespace, range(NBR_CHURN_ALLOCATED))
    churned = range(NBR_CHURN_ALLOCATED, NBR_CHURN_ALLOCATED + NBR_CHURN_DELETED)
    churned_prefixes, churned_addresses = await _allocate_on_default(db, dataset, namespace, churned)
    for node in churned_prefixes + churned_addresses:
        await node.delete(db=db)


DATASET_BUILDERS: dict[str, Callable[[InfrahubDatabase, PoolDataset, Node], Awaitable[None]]] = {
    "branches": _build_branches_dataset,
    "churn": _build_churn_dataset,
}


@pytest.fixture(scope="module", params=list(DATASET_BUILDERS))
async def dataset(db: InfrahubDatabase, request: pytest.FixtureRequest) -> PoolDataset:
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
    await load_schema(db=db, schema=IPAM_SCHEMA)
    registry.node[InfrahubKind.IPPREFIXPOOL] = CoreIPPrefixPool
    registry.node[InfrahubKind.IPADDRESSPOOL] = CoreIPAddressPool
    default_namespace = await create_ipam_namespace(db=db)
    registry.default_ipnamespace = default_namespace.id

    dataset = PoolDataset(default_branch=default_branch)
    namespace = await _create(db, default_branch, InfrahubKind.NAMESPACE, name="benchmark-ns")
    prefix_resource = await _create(
        db, default_branch, "IpamIPPrefix", prefix=str(PREFIX_RESOURCE), ip_namespace=namespace
    )
    address_resource = await _create(
        db, default_branch, "IpamIPPrefix", prefix=str(ADDRESS_RESOURCE), ip_namespace=namespace
    )
    prefix_pool = await _create(
        db,
        default_branch,
        InfrahubKind.IPPREFIXPOOL,
        name="benchmark-prefix-pool",
        resources=[prefix_resource],
        ip_namespace=namespace,
        default_prefix_length=ALLOCATED_PREFIX_LENGTH,
    )
    address_pool = await _create(
        db,
        default_branch,
        InfrahubKind.IPADDRESSPOOL,
        name="benchmark-address-pool",
        resources=[address_resource],
        ip_namespace=namespace,
        default_address_type="IpamIPAddress",
    )
    dataset.pool_ids = {InfrahubKind.IPPREFIXPOOL: prefix_pool.id, InfrahubKind.IPADDRESSPOOL: address_pool.id}

    await DATASET_BUILDERS[request.param](db, dataset, namespace)
    return dataset


@pytest.mark.parametrize("case", POOL_BENCHMARK_CASES, ids=lambda case: case.name)
def test_ip_pool_next_free(
    exec_async: Callable[..., Any],
    aio_benchmark: Callable[..., Any],
    benchmark: BenchmarkFixture,
    db: InfrahubDatabase,
    dataset: PoolDataset,
    case: PoolBenchmarkCase,
) -> None:
    branch = dataset.branches[0] if case.on_branch else dataset.default_branch
    pool_id = dataset.pool_ids[case.pool_kind]

    async def next_free(query_db: InfrahubDatabase = db) -> str:
        # A pool loaded once keeps its peers in memory, so each lookup loads it again to count reading them.
        pool = await NodeManager.get_one(db=query_db, id=pool_id, branch=branch, raise_on_error=True)
        if isinstance(pool, CoreIPPrefixPool):
            return str(await pool.get_next(db=query_db, prefixlen=ALLOCATED_PREFIX_LENGTH))
        assert isinstance(pool, CoreIPAddressPool)
        return str(await pool.get_next(db=query_db))

    for _ in range(NBR_WARMUP):
        exec_async(next_free)

    profiling_db = ProfilingInfrahubDatabase.from_db(db=db)
    assert isinstance(profiling_db, ProfilingInfrahubDatabase)
    benchmark.extra_info["next_free"] = exec_async(next_free, query_db=profiling_db)
    benchmark.extra_info["db_hits"] = sum(profiling_db.db_hits.values())
    benchmark.extra_info["db_hits_by_query"] = dict(profiling_db.db_hits)
    benchmark.extra_info["queries"] = dict(profiling_db.query_counts)
    benchmark.extra_info["branches"] = len(dataset.branches)
    benchmark.extra_info["allocations"] = dataset.allocations[
        "prefix" if case.pool_kind == InfrahubKind.IPPREFIXPOOL else "address"
    ]
    aio_benchmark(next_free)
