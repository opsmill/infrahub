from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import pytest

from infrahub.core.manager import NodeManager

from .conftest import SCOPED_POOL_START, scoped_device, scoped_site

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.node.resource_manager.number_pool import CoreNumberPool
    from infrahub.database import InfrahubDatabase


@dataclass(frozen=True)
class ScopedPoolCase:
    name: str
    pool_fixture: str
    stored_scope: list[str] | None


SCOPED_POOL_CASES = [
    ScopedPoolCase(name="one-element", pool_fixture="site_scoped_pool", stored_scope=["site"]),
    ScopedPoolCase(name="two-elements", pool_fixture="site_role_scoped_pool", stored_scope=["site", "role"]),
    ScopedPoolCase(name="list-attribute", pool_fixture="tags_scoped_pool", stored_scope=["tags"]),
    ScopedPoolCase(name="unscoped", pool_fixture="unscoped_device_pool", stored_scope=None),
]


@pytest.fixture
async def scoped_pools(
    site_scoped_pool: CoreNumberPool,
    site_role_scoped_pool: CoreNumberPool,
    tags_scoped_pool: CoreNumberPool,
    unscoped_device_pool: CoreNumberPool,
) -> dict[str, CoreNumberPool]:
    return {
        "site_scoped_pool": site_scoped_pool,
        "site_role_scoped_pool": site_role_scoped_pool,
        "tags_scoped_pool": tags_scoped_pool,
        "unscoped_device_pool": unscoped_device_pool,
    }


@pytest.mark.parametrize("case", SCOPED_POOL_CASES, ids=[case.name for case in SCOPED_POOL_CASES])
async def test_device_takes_the_first_number_of_a_new_pool(
    db: InfrahubDatabase, default_branch: Branch, scoped_pools: dict[str, CoreNumberPool], case: ScopedPoolCase
) -> None:
    pool = scoped_pools[case.pool_fixture]
    site = await scoped_site(db=db, branch=default_branch, name="site-a")

    device = await scoped_device(db=db, branch=default_branch, pool=pool, name="device-a1", site=site)

    stored_pool = await NodeManager.get_one(db=db, branch=default_branch, id=pool.id, raise_on_error=True)
    assert stored_pool.get_attribute("allocation_scope").value == case.stored_scope
    assert device.get_attribute("vlan_id").value == SCOPED_POOL_START
