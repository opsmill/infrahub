from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import pytest

from infrahub.core.manager import NodeManager

from .conftest import SCOPED_POOL_START, scoped_device, scoped_pool, scoped_site

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase


@dataclass(frozen=True)
class ScopedPoolCase:
    name: str
    allocation_scope: list[str] | None


SCOPED_POOL_CASES = [
    ScopedPoolCase(name="one-element", allocation_scope=["site"]),
    ScopedPoolCase(name="two-elements", allocation_scope=["site", "role"]),
    ScopedPoolCase(name="unscoped", allocation_scope=None),
]


@pytest.mark.parametrize("case", SCOPED_POOL_CASES, ids=[case.name for case in SCOPED_POOL_CASES])
async def test_device_takes_the_first_number_of_a_new_pool(
    db: InfrahubDatabase, default_branch: Branch, scoped_schema: None, case: ScopedPoolCase
) -> None:
    pool = await scoped_pool(db=db, name=f"vlan-{case.name}", allocation_scope=case.allocation_scope)
    site = await scoped_site(db=db, branch=default_branch, name="site-a")

    device = await scoped_device(db=db, branch=default_branch, pool=pool, name="device-a1", site=site)

    stored_pool = await NodeManager.get_one(db=db, branch=default_branch, id=pool.id, raise_on_error=True)
    assert stored_pool.get_attribute("allocation_scope").value == case.allocation_scope
    assert device.get_attribute("vlan_id").value == SCOPED_POOL_START
