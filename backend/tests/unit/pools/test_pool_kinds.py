from __future__ import annotations

from dataclasses import dataclass

import pytest

from infrahub.core.constants import InfrahubKind
from infrahub.core.schema import GenericSchema, MainSchemaTypes, NodeSchema
from infrahub.pools.pool_kinds import is_resource_pool_schema


@dataclass(frozen=True, kw_only=True)
class PoolKindCase:
    name: str
    schema: MainSchemaTypes
    expected: bool


POOL_KIND_CASES = [
    PoolKindCase(
        name="number_pool",
        schema=NodeSchema(name="NumberPool", namespace="Core", inherit_from=[InfrahubKind.RESOURCEPOOL]),
        expected=True,
    ),
    PoolKindCase(
        name="ip_prefix_pool",
        schema=NodeSchema(
            name="IPPrefixPool", namespace="Core", inherit_from=[InfrahubKind.RESOURCEPOOL, InfrahubKind.IPPOOL]
        ),
        expected=True,
    ),
    PoolKindCase(
        name="resource_pool_generic", schema=GenericSchema(name="ResourcePool", namespace="Core"), expected=True
    ),
    PoolKindCase(name="number_pool_range", schema=NodeSchema(name="NumberPoolRange", namespace="Core"), expected=True),
    PoolKindCase(name="other_node", schema=NodeSchema(name="Ticket", namespace="Testing"), expected=False),
    PoolKindCase(name="other_generic", schema=GenericSchema(name="Device", namespace="Testing"), expected=False),
]


@pytest.mark.parametrize("case", [pytest.param(case, id=case.name) for case in POOL_KIND_CASES])
def test_only_resource_pools_and_their_ranges_are_pool_kinds(case: PoolKindCase) -> None:
    assert is_resource_pool_schema(schema=case.schema) is case.expected
