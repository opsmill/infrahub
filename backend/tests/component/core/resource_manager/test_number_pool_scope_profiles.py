from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import pytest

from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.node.create import create_node
from infrahub.profiles.queries.get_profile_data import GetProfileDataQuery
from tests.adapters.lock.timeline import LockAction
from tests.helpers.db_query_counter import CountingInfrahubDatabase
from tests.helpers.number_pool import (
    SCOPED_DEVICE,
    SCOPED_RACK,
    pool_lock_events,
    scoped_device_holding,
    scoped_pool,
    scoped_site,
    vlan_id,
)

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.node.resource_manager.number_pool import CoreNumberPool
    from infrahub.database import InfrahubDatabase
    from tests.adapters.lock.timeline import LockTimeline


@dataclass
class ProfileDataset:
    """Three pools over the device's `vlan_id`, the numbers their divisions hold, and four device profiles.

    The pool scoped by `site`: site-a holds 1, site-b holds 1 to 3 and site-c holds 1. The pool scoped by `site`
    and `role`: the spines of site-a hold 1. The pool scoped by the optional `rack`: rack-1 holds 1. The profiles set
    site-a, site-b, site-a with the role spine, and site-a with rack-1.
    """

    default_branch: Branch
    pools: dict[str, CoreNumberPool]
    sites: dict[str, Node]
    racks: dict[str, Node]
    profiles: dict[str, Node]


@dataclass
class ProfileScopeCase:
    name: str
    pool: str
    profile: str
    payload_site: str | None
    payload_role: str | None
    expected_site: str
    expected_division: tuple[str, ...]
    expected_number: int
    expected_profile_reads: int


PROFILE_SCOPE_CASES = [
    ProfileScopeCase(
        name="site-set-by-the-profile",
        pool="site",
        profile="site-a",
        payload_site=None,
        payload_role="leaf",
        expected_site="site-a",
        expected_division=("site-a",),
        expected_number=2,
        # The preview and the write each read the profiles once, for the mandatory fields and the division together,
        # and the saved device reads them once more to apply them.
        expected_profile_reads=3,
    ),
    ProfileScopeCase(
        name="site-and-role-set-by-the-profile",
        pool="site-and-role",
        profile="site-a-spine",
        payload_site=None,
        payload_role=None,
        expected_site="site-a",
        expected_division=("site-a", "spine"),
        expected_number=2,
        expected_profile_reads=3,
    ),
    ProfileScopeCase(
        name="site-of-the-payload-over-the-site-of-the-profile",
        pool="site",
        profile="site-b",
        payload_site="site-c",
        payload_role="leaf",
        expected_site="site-c",
        expected_division=("site-c",),
        expected_number=2,
        # Only the saved device reads the profiles, because the payload sets every element of the scope.
        expected_profile_reads=1,
    ),
    ProfileScopeCase(
        name="optional-rack-set-by-the-profile",
        pool="rack",
        profile="site-a-rack-1",
        payload_site=None,
        payload_role="leaf",
        expected_site="site-a",
        expected_division=("rack-1",),
        expected_number=2,
        # The mandatory fields leave the optional rack out, so their read covers it only by reading every field.
        expected_profile_reads=3,
    ),
]


class TestScopeElementSetByAProfile:
    """Every test writes one device in a division that no other test of the class writes in."""

    @pytest.fixture(scope="class")
    async def dataset(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, scoped_schema_scope_class: None
    ) -> ProfileDataset:
        branch = default_branch_scope_class
        pools = {
            "site": await scoped_pool(db=db, name="vlan-per-site", allocation_scope=["site"]),
            "site-and-role": await scoped_pool(db=db, name="vlan-per-site-and-role", allocation_scope=["site", "role"]),
            "rack": await scoped_pool(db=db, name="vlan-per-rack", allocation_scope=["rack"]),
        }
        sites = {name: await scoped_site(db=db, branch=branch, name=name) for name in ("site-a", "site-b", "site-c")}
        for site_name, numbers in (("site-a", [1]), ("site-b", [1, 2, 3]), ("site-c", [1])):
            for number in numbers:
                await scoped_device_holding(
                    db=db,
                    branch=branch,
                    pool=pools["site"],
                    name=f"{site_name}-holder-{number}",
                    site=sites[site_name],
                    number=number,
                )
        await scoped_device_holding(
            db=db,
            branch=branch,
            pool=pools["site-and-role"],
            name="site-a-spine-holder-1",
            site=sites["site-a"],
            number=1,
            role="spine",
        )
        rack = await Node.init(db=db, schema=SCOPED_RACK.kind, branch=branch)
        await rack.new(db=db, name="rack-1")
        await rack.save(db=db)
        racks = {"rack-1": rack}
        rack_holder = await Node.init(db=db, schema=SCOPED_DEVICE.kind, branch=branch)
        await rack_holder.new(
            db=db,
            name="rack-1-holder-1",
            role="leaf",
            tags=["red"],
            site=sites["site-a"],
            rack=rack,
            vlan_id={"value": 1, "from_pool": {"id": pools["rack"].id}},
        )
        await rack_holder.save(db=db)
        profiles = {}
        for profile_name, site_name, role, rack_name in (
            ("site-a", "site-a", None, None),
            ("site-b", "site-b", None, None),
            ("site-a-spine", "site-a", "spine", None),
            ("site-a-rack-1", "site-a", None, "rack-1"),
        ):
            profile = await Node.init(db=db, schema=f"Profile{SCOPED_DEVICE.kind}", branch=branch)
            await profile.new(
                db=db,
                profile_name=profile_name,
                profile_priority=1000,
                site=sites[site_name],
                role=role,
                rack=racks[rack_name] if rack_name else None,
            )
            await profile.save(db=db)
            profiles[profile_name] = profile
        return ProfileDataset(default_branch=branch, pools=pools, sites=sites, racks=racks, profiles=profiles)

    @pytest.mark.parametrize("case", PROFILE_SCOPE_CASES, ids=[case.name for case in PROFILE_SCOPE_CASES])
    async def test_the_division_includes_the_scope_elements_a_profile_sets(
        self,
        db: InfrahubDatabase,
        dataset: ProfileDataset,
        recording_lock_timeline: LockTimeline,
        case: ProfileScopeCase,
    ) -> None:
        branch = dataset.default_branch
        pool = dataset.pools[case.pool]
        payload: dict[str, Any] = {
            "name": {"value": f"device-of-{case.name}"},
            "tags": {"value": ["red"]},
            "vlan_id": {"from_pool": {"id": pool.id}},
            "profiles": [{"id": dataset.profiles[case.profile].id}],
        }
        if case.payload_site is not None:
            payload["site"] = {"id": dataset.sites[case.payload_site].id}
        if case.payload_role is not None:
            payload["role"] = {"value": case.payload_role}
        peers = {**dataset.sites, **dataset.racks}
        division_key = ".".join(
            peers[element].id if element in peers else element for element in case.expected_division
        )
        expected_lock_name = f"resource_pool.{pool.id}.{division_key}"
        counting_db = CountingInfrahubDatabase.from_db(db=db)
        start = recording_lock_timeline.checkpoint("write")

        device = await create_node(
            data=payload,
            db=counting_db,
            branch=branch,
            schema=db.schema.get(name=SCOPED_DEVICE.kind, branch=branch, duplicate=False),
        )

        stored = await NodeManager.get_one(db=db, branch=branch, id=device.id, raise_on_error=True)
        stored_site = await stored.get_relationship("site").get_peer(db=db)
        assert stored_site is not None
        assert stored_site.id == dataset.sites[case.expected_site].id
        assert vlan_id(stored) == case.expected_number
        assert pool_lock_events(timeline=recording_lock_timeline, pool=pool, after=start) == [
            (expected_lock_name, LockAction.ACQUIRE),
            (expected_lock_name, LockAction.RELEASE),
        ]
        assert counting_db.count_for(GetProfileDataQuery.name) == case.expected_profile_reads
