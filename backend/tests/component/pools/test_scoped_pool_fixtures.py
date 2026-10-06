from infrahub.core.branch import Branch
from infrahub.core.manager import NodeManager
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.database import InfrahubDatabase
from infrahub.pools.number_pool_repository import NumberPoolRepository
from tests.helpers.number_pool import (
    SCOPED_DEVICE_ATTRIBUTE,
    SCOPED_DEVICE_KIND,
    create_sites_with_devices,
    create_two_range_pool,
)


async def test_sites_hold_their_devices(
    db: InfrahubDatabase, default_branch: Branch, scoped_pool_schema: SchemaBranch
) -> None:
    created = await create_sites_with_devices(db=db, branch=default_branch, sites=2, devices_per_site=3)

    devices = await NodeManager.query(
        db=db, schema=SCOPED_DEVICE_KIND, branch=default_branch, prefetch_relationships=True
    )
    by_site: dict[str, list[str]] = {}
    for device in devices:
        site = await device.get_relationship("site").get_peer(db=db)
        assert site is not None
        by_site.setdefault(site.get_attribute("name").value, []).append(str(device.get_attribute("name").value))
        assert device.get_attribute(SCOPED_DEVICE_ATTRIBUTE).value is None
        assert device.get_attribute("role").value == "leaf"

    assert {name: sorted(names) for name, names in by_site.items()} == {
        "site-1": ["site-1-device-1", "site-1-device-2", "site-1-device-3"],
        "site-2": ["site-2-device-1", "site-2-device-2", "site-2-device-3"],
    }
    assert [len(item.devices) for item in created] == [3, 3]


async def test_two_range_pool_has_weighted_and_unweighted_ranges(
    db: InfrahubDatabase, default_branch: Branch, scoped_pool_schema: SchemaBranch
) -> None:
    pool, _ = await create_two_range_pool(db=db)

    ranges = await NumberPoolRepository(db=db).get_ranges(pool_id=pool.get_id())
    assert [(item.start.value, item.end.value, item.allocation_weight.value) for item in ranges] == [
        (1, 50, 10),
        (51, 100, None),
    ]
    assert pool.get_attribute("node").value == SCOPED_DEVICE_KIND
    assert pool.get_attribute("node_attribute").value == SCOPED_DEVICE_ATTRIBUTE
    assert pool.get_attribute("start_range").value is None
    assert pool.get_attribute("end_range").value is None
