from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from infrahub.core import registry
from infrahub.core.constants import InfrahubKind
from infrahub.core.manager import NodeManager
from infrahub.core.node.resource_manager.number_pool import CoreNumberPool
from infrahub.graphql.initialization import prepare_graphql_params
from tests.helpers.graphql import graphql
from tests.helpers.number_pool import (
    SCOPED_POOL_SCHEMA,
    scoped_device,
    scoped_pool,
    scoped_site,
    vlan_id,
)
from tests.helpers.schema import load_schema

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase


MOVE_DEVICE_AND_ALLOCATE = """
mutation MoveDeviceAndAllocate($device_id: String!, $site_id: String!, $pool_id: String!) {
    ScopeDeviceUpdate(data: {
        id: $device_id
        site: { id: $site_id }
        vlan_id: { value: null, from_pool: { id: $pool_id } }
    }) {
        ok
        object { vlan_id { value } }
    }
}
"""


@pytest.fixture
async def scoped_schema(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> None:
    """The scoped pool test schema, saved on the default branch so that its fields hold the ids a scope stores."""
    await load_schema(db=db, schema=SCOPED_POOL_SCHEMA, update_db=True)
    registry.node[InfrahubKind.NUMBERPOOL] = CoreNumberPool


@pytest.fixture
async def site_scoped_pool(db: InfrahubDatabase, scoped_schema: None) -> CoreNumberPool:
    return await scoped_pool(db=db, name="vlan-per-site", allocation_scope=["site"])


async def test_an_update_that_moves_a_device_allocates_in_the_new_site(
    db: InfrahubDatabase, default_branch: Branch, site_scoped_pool: CoreNumberPool
) -> None:
    site_a = await scoped_site(db=db, branch=default_branch, name="site-a")
    site_b = await scoped_site(db=db, branch=default_branch, name="site-b")
    device_a1 = await scoped_device(db=db, branch=default_branch, pool=site_scoped_pool, name="device-a1", site=site_a)
    for name in ("device-b1", "device-b2"):
        await scoped_device(db=db, branch=default_branch, pool=site_scoped_pool, name=name, site=site_b)
    gql_params = await prepare_graphql_params(db=db, branch=default_branch)

    result = await graphql(
        schema=gql_params.schema,
        source=MOVE_DEVICE_AND_ALLOCATE,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"device_id": device_a1.id, "site_id": site_b.id, "pool_id": site_scoped_pool.id},
    )

    assert result.errors is None
    assert result.data
    assert result.data["ScopeDeviceUpdate"]["object"]["vlan_id"]["value"] == 3
    stored = await NodeManager.get_one(db=db, branch=default_branch, id=device_a1.id, raise_on_error=True)
    assert vlan_id(stored) == 3
