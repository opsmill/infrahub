from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import pytest

from infrahub.core import registry
from infrahub.core.constants import RelationshipDirection
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.migrations.query.node_duplicate import NodeDuplicateQuery, SchemaNodeInfo
from infrahub.pools.number_pool_repository import NumberPoolRepository
from infrahub.pools.number_ranges import EffectiveSpace, NumberDomain
from infrahub.pools.scope import Division, DivisionElementPath
from tests.component.core.resource_manager.conftest import delete_branch
from tests.helpers.number_pool import (
    SCOPED_CIRCUIT,
    SCOPED_DEVICE,
    SCOPED_POOL_END,
    SCOPED_POOL_START,
    scoped_circuit,
    scoped_device,
    scoped_device_holding,
    scoped_pool,
    scoped_site,
)

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.node.resource_manager.number_pool import CoreNumberPool
    from infrahub.database import InfrahubDatabase


SITE_PATH = DivisionElementPath(name="scope_device__site", relationship_direction=RelationshipDirection.BIDIR)
ROLE_PATH = DivisionElementPath(name="role")
A_SITE_PATH = DivisionElementPath(name="scope_circuit__site", relationship_direction=RelationshipDirection.OUTBOUND)
Z_SITE_PATH = DivisionElementPath(name="scope_circuit__site", relationship_direction=RelationshipDirection.INBOUND)


@dataclass(frozen=True)
class ScopedPoolCase:
    name: str
    allocation_scope: list[str] | None


SCOPED_POOL_CASES = [
    ScopedPoolCase(name="one-element", allocation_scope=["site"]),
    ScopedPoolCase(name="two-elements", allocation_scope=["site", "role"]),
    ScopedPoolCase(name="unscoped", allocation_scope=None),
]


def expected_stored_scope(names: list[str] | None) -> list[dict[str, str]] | None:
    if not names:
        return None
    device = registry.schema.get(name=SCOPED_DEVICE.kind, duplicate=False)
    expected: list[dict[str, str]] = []
    for name in names:
        field = device.get_attribute_or_none(name=name) or device.get_relationship(name=name)
        assert field.id
        expected.append({"id": field.id, "name": name})
    return expected


@pytest.mark.parametrize("case", SCOPED_POOL_CASES, ids=[case.name for case in SCOPED_POOL_CASES])
async def test_device_takes_the_first_number_of_a_new_pool(
    db: InfrahubDatabase, default_branch: Branch, scoped_schema: None, case: ScopedPoolCase
) -> None:
    pool = await scoped_pool(db=db, name=f"vlan-{case.name}", allocation_scope=case.allocation_scope)
    site = await scoped_site(db=db, branch=default_branch, name="site-a")

    device = await scoped_device(db=db, branch=default_branch, pool=pool, name="device-a1", site=site)

    stored_pool = await NodeManager.get_one(db=db, branch=default_branch, id=pool.id, raise_on_error=True)
    assert stored_pool.get_attribute("allocation_scope").value == expected_stored_scope(names=case.allocation_scope)
    assert device.get_attribute("vlan_id").value == SCOPED_POOL_START


async def used_numbers(
    db: InfrahubDatabase, pool: CoreNumberPool, branch: Branch, division: Division | None = None
) -> list[int]:
    repository = NumberPoolRepository(db=db)
    space = EffectiveSpace(ranges=await repository.get_pool_ranges(pool_id=pool.get_id()), domain=NumberDomain())
    if division is None:
        return await repository.get_used(pool=pool, branch=branch, space=space)
    return await repository.get_used(pool=pool, branch=branch, space=space, division=division)


async def lowest_free_number(
    db: InfrahubDatabase, pool: CoreNumberPool, branch: Branch, division: Division | None = None
) -> int | None:
    repository = NumberPoolRepository(db=db)
    if division is None:
        return await repository.get_free(
            pool=pool, branch=branch, min_value=SCOPED_POOL_START, max_value=SCOPED_POOL_END
        )
    return await repository.get_free(
        pool=pool, branch=branch, min_value=SCOPED_POOL_START, max_value=SCOPED_POOL_END, division=division
    )


async def test_a_division_reads_only_the_numbers_of_its_nodes(
    db: InfrahubDatabase, default_branch: Branch, site_scoped_pool: CoreNumberPool
) -> None:
    site_a = await scoped_site(db=db, branch=default_branch, name="site-a")
    site_b = await scoped_site(db=db, branch=default_branch, name="site-b")
    for name, site, number in (("device-a1", site_a, 1), ("device-a2", site_a, 2), ("device-b1", site_b, 1)):
        await scoped_device_holding(
            db=db, branch=default_branch, pool=site_scoped_pool, name=name, site=site, number=number
        )
    division_a = Division(elements=(SITE_PATH,), values=(site_a.id,))
    division_b = Division(elements=(SITE_PATH,), values=(site_b.id,))

    assert await used_numbers(db=db, pool=site_scoped_pool, branch=default_branch, division=division_a) == [1, 2]
    assert await used_numbers(db=db, pool=site_scoped_pool, branch=default_branch, division=division_b) == [1]
    assert await lowest_free_number(db=db, pool=site_scoped_pool, branch=default_branch, division=division_a) == 3
    assert await lowest_free_number(db=db, pool=site_scoped_pool, branch=default_branch, division=division_b) == 2


async def test_a_directional_scope_element_reads_only_the_peer_on_its_side(
    db: InfrahubDatabase, default_branch: Branch, circuit_schema: None
) -> None:
    """Each circuit links to site A and site B through Relationship vertices of one name, in opposite directions."""
    pool = await scoped_pool(db=db, name="vlan-per-a-site", allocation_scope=["a_site"], kind=SCOPED_CIRCUIT.kind)
    site_a = await scoped_site(db=db, branch=default_branch, name="site-a")
    site_b = await scoped_site(db=db, branch=default_branch, name="site-b")
    await scoped_circuit(
        db=db, branch=default_branch, pool=pool, name="circuit-a-to-b", a_site=site_a, z_site=site_b, number=1
    )
    await scoped_circuit(
        db=db, branch=default_branch, pool=pool, name="circuit-b-to-a", a_site=site_b, z_site=site_a, number=2
    )

    used_per_division = {
        (end, site_name): await used_numbers(
            db=db, pool=pool, branch=default_branch, division=Division(elements=(path,), values=(site.id,))
        )
        for end, path in (("a_site", A_SITE_PATH), ("z_site", Z_SITE_PATH))
        for site_name, site in (("site-a", site_a), ("site-b", site_b))
    }

    assert used_per_division == {
        ("a_site", "site-a"): [1],
        ("a_site", "site-b"): [2],
        ("z_site", "site-a"): [2],
        ("z_site", "site-b"): [1],
    }


async def test_a_two_element_division_matches_both_values(
    db: InfrahubDatabase, default_branch: Branch, site_role_scoped_pool: CoreNumberPool
) -> None:
    site_a = await scoped_site(db=db, branch=default_branch, name="site-a")
    for name, role, number in (("device-a1", "leaf", 1), ("device-a2", "spine", 1), ("device-a3", "leaf", 2)):
        await scoped_device_holding(
            db=db, branch=default_branch, pool=site_role_scoped_pool, name=name, site=site_a, number=number, role=role
        )
    leaves = Division(elements=(SITE_PATH, ROLE_PATH), values=(site_a.id, "leaf"))
    spines = Division(elements=(SITE_PATH, ROLE_PATH), values=(site_a.id, "spine"))

    assert await used_numbers(db=db, pool=site_role_scoped_pool, branch=default_branch, division=leaves) == [1, 2]
    assert await used_numbers(db=db, pool=site_role_scoped_pool, branch=default_branch, division=spines) == [1]
    assert await lowest_free_number(db=db, pool=site_role_scoped_pool, branch=default_branch, division=spines) == 2


async def test_a_node_with_an_empty_value_belongs_to_the_division_of_the_empty_value(
    db: InfrahubDatabase, default_branch: Branch, site_role_scoped_pool: CoreNumberPool
) -> None:
    site_a = await scoped_site(db=db, branch=default_branch, name="site-a")
    await scoped_device_holding(
        db=db, branch=default_branch, pool=site_role_scoped_pool, name="device-a1", site=site_a, number=1, role=""
    )

    assert await used_numbers(
        db=db,
        pool=site_role_scoped_pool,
        branch=default_branch,
        division=Division(elements=(SITE_PATH, ROLE_PATH), values=(site_a.id, "")),
    ) == [1]
    assert (
        await used_numbers(
            db=db,
            pool=site_role_scoped_pool,
            branch=default_branch,
            division=Division(elements=(SITE_PATH, ROLE_PATH), values=(site_a.id, "leaf")),
        )
        == []
    )


async def test_a_node_moved_on_a_branch_counts_under_both_sites_on_every_branch(
    db: InfrahubDatabase, default_branch: Branch, site_scoped_pool: CoreNumberPool
) -> None:
    site_a = await scoped_site(db=db, branch=default_branch, name="site-a")
    site_c = await scoped_site(db=db, branch=default_branch, name="site-c")
    device = await scoped_device_holding(
        db=db, branch=default_branch, pool=site_scoped_pool, name="device-1", site=site_a, number=5
    )
    branch = await create_branch(branch_name="moves-device-1", db=db)
    moved = await NodeManager.get_one(db=db, branch=branch, id=device.id, raise_on_error=True)
    await moved.get_relationship(name="site").update(db=db, data=site_c)
    await moved.save(db=db)
    division_a = Division(elements=(SITE_PATH,), values=(site_a.id,))
    division_c = Division(elements=(SITE_PATH,), values=(site_c.id,))

    for reading_branch in (default_branch, branch):
        assert await used_numbers(db=db, pool=site_scoped_pool, branch=reading_branch, division=division_a) == [5]
        assert await used_numbers(db=db, pool=site_scoped_pool, branch=reading_branch, division=division_c) == [5]


async def test_a_node_moved_on_the_default_branch_still_counts_under_the_site_an_older_branch_reads(
    db: InfrahubDatabase, default_branch: Branch, site_scoped_pool: CoreNumberPool
) -> None:
    site_a = await scoped_site(db=db, branch=default_branch, name="site-a")
    site_c = await scoped_site(db=db, branch=default_branch, name="site-c")
    device = await scoped_device_holding(
        db=db, branch=default_branch, pool=site_scoped_pool, name="device-1", site=site_a, number=5
    )
    await create_branch(branch_name="forked-in-site-a", db=db)
    moved = await NodeManager.get_one(db=db, branch=default_branch, id=device.id, raise_on_error=True)
    await moved.get_relationship(name="site").update(db=db, data=site_c)
    await moved.save(db=db)
    division_a = Division(elements=(SITE_PATH,), values=(site_a.id,))
    division_c = Division(elements=(SITE_PATH,), values=(site_c.id,))

    assert await used_numbers(db=db, pool=site_scoped_pool, branch=default_branch, division=division_a) == [5]
    assert await used_numbers(db=db, pool=site_scoped_pool, branch=default_branch, division=division_c) == [5]


async def test_a_node_that_exists_only_on_another_branch_counts_on_every_branch(
    db: InfrahubDatabase, default_branch: Branch, site_scoped_pool: CoreNumberPool
) -> None:
    site_a = await scoped_site(db=db, branch=default_branch, name="site-a")
    branch = await create_branch(branch_name="creates-device-1", db=db)
    await scoped_device_holding(
        db=db, branch=branch, pool=site_scoped_pool, name="device-1", site=site_a, number=SCOPED_POOL_START
    )
    division_a = Division(elements=(SITE_PATH,), values=(site_a.id,))

    assert await used_numbers(db=db, pool=site_scoped_pool, branch=default_branch, division=division_a) == [
        SCOPED_POOL_START
    ]
    assert (
        await lowest_free_number(db=db, pool=site_scoped_pool, branch=default_branch, division=division_a)
        == SCOPED_POOL_START + 1
    )


async def test_deleting_the_branch_that_moved_a_node_frees_its_number_in_the_new_site(
    db: InfrahubDatabase, default_branch: Branch, site_scoped_pool: CoreNumberPool
) -> None:
    site_a = await scoped_site(db=db, branch=default_branch, name="site-a")
    site_c = await scoped_site(db=db, branch=default_branch, name="site-c")
    device = await scoped_device_holding(
        db=db, branch=default_branch, pool=site_scoped_pool, name="device-1", site=site_a, number=5
    )
    branch = await create_branch(branch_name="moves-device-1", db=db)
    moved = await NodeManager.get_one(db=db, branch=branch, id=device.id, raise_on_error=True)
    await moved.get_relationship(name="site").update(db=db, data=site_c)
    await moved.save(db=db)
    division_c = Division(elements=(SITE_PATH,), values=(site_c.id,))

    await delete_branch(db=db, branch=branch)

    assert await used_numbers(db=db, pool=site_scoped_pool, branch=default_branch, division=division_c) == []


async def test_a_role_changed_on_a_branch_counts_under_both_roles(
    db: InfrahubDatabase, default_branch: Branch, site_role_scoped_pool: CoreNumberPool
) -> None:
    site_a = await scoped_site(db=db, branch=default_branch, name="site-a")
    device = await scoped_device_holding(
        db=db, branch=default_branch, pool=site_role_scoped_pool, name="device-1", site=site_a, number=3, role="leaf"
    )
    branch = await create_branch(branch_name="makes-device-1-a-spine", db=db)
    changed = await NodeManager.get_one(db=db, branch=branch, id=device.id, raise_on_error=True)
    changed.get_attribute("role").value = "spine"
    await changed.save(db=db)

    for role in ("leaf", "spine"):
        division = Division(elements=(SITE_PATH, ROLE_PATH), values=(site_a.id, role))
        assert await used_numbers(db=db, pool=site_role_scoped_pool, branch=default_branch, division=division) == [3]


async def test_a_node_copied_by_a_kind_migration_counts_under_the_site_of_each_copy(
    db: InfrahubDatabase, default_branch: Branch, site_scoped_pool: CoreNumberPool
) -> None:
    """The migration leaves the old Node vertex live on a branch that moved it to site C and a new one in site A."""
    site_a = await scoped_site(db=db, branch=default_branch, name="site-a")
    site_c = await scoped_site(db=db, branch=default_branch, name="site-c")
    device = await scoped_device_holding(
        db=db, branch=default_branch, pool=site_scoped_pool, name="device-1", site=site_a, number=5
    )
    branch = await create_branch(branch_name="moves-device-1", db=db)
    moved = await NodeManager.get_one(db=db, branch=branch, id=device.id, raise_on_error=True)
    await moved.get_relationship(name="site").update(db=db, data=site_c)
    await moved.save(db=db)
    migration = await NodeDuplicateQuery.init(
        db=db,
        branch=default_branch,
        kind_updates_map={
            SCOPED_DEVICE.kind: SchemaNodeInfo(
                name="Machine", namespace="Scope", labels=["ScopeMachine"], kind="ScopeMachine"
            )
        },
    )
    await migration.execute(db=db)
    division_a = Division(elements=(SITE_PATH,), values=(site_a.id,))
    division_c = Division(elements=(SITE_PATH,), values=(site_c.id,))

    assert await used_numbers(db=db, pool=site_scoped_pool, branch=default_branch, division=division_a) == [5]
    assert await used_numbers(db=db, pool=site_scoped_pool, branch=default_branch, division=division_c) == [5]


async def test_a_reservation_is_read_only_in_the_division_of_its_node(
    db: InfrahubDatabase, default_branch: Branch, site_scoped_pool: CoreNumberPool
) -> None:
    site_a = await scoped_site(db=db, branch=default_branch, name="site-a")
    site_b = await scoped_site(db=db, branch=default_branch, name="site-b")
    device = await scoped_device_holding(
        db=db, branch=default_branch, pool=site_scoped_pool, name="device-a1", site=site_a, number=4
    )
    repository = NumberPoolRepository(db=db)

    async def reservation(division: Division | None) -> int | None:
        return await repository.get_reservation(
            pool_id=site_scoped_pool.id, branch=default_branch, identifier=device.id, division=division
        )

    assert await reservation(division=None) == 4
    assert await reservation(division=Division(elements=(SITE_PATH,), values=(site_a.id,))) == 4
    assert await reservation(division=Division(elements=(SITE_PATH,), values=(site_b.id,))) is None


async def test_without_a_division_every_tracked_number_is_read(
    db: InfrahubDatabase, default_branch: Branch, site_scoped_pool: CoreNumberPool
) -> None:
    site_a = await scoped_site(db=db, branch=default_branch, name="site-a")
    site_b = await scoped_site(db=db, branch=default_branch, name="site-b")
    for name, site, number in (("device-a1", site_a, 1), ("device-a2", site_a, 2), ("device-b1", site_b, 4)):
        await scoped_device_holding(
            db=db, branch=default_branch, pool=site_scoped_pool, name=name, site=site, number=number
        )

    assert await used_numbers(db=db, pool=site_scoped_pool, branch=default_branch) == [1, 2, 4]
    assert await lowest_free_number(db=db, pool=site_scoped_pool, branch=default_branch) == 3
