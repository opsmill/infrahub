from __future__ import annotations

import re
from typing import TYPE_CHECKING

import pytest

from infrahub.core import registry
from infrahub.core.constants import SYSTEM_USER_ID, InfrahubKind
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.node.create import create_node
from infrahub.core.node.resource_manager.number_pool import CoreNumberPool
from infrahub.core.schema import AttributeSchema, NodeSchema, SchemaRoot
from infrahub.core.timestamp import Timestamp
from infrahub.database.validation import verify_graph
from infrahub.exceptions import DivisionExhaustedError, PoolExhaustedError
from infrahub.pools.division_reader import NodeNumberPoolDivisionReader
from infrahub.pools.existing_node_numbers import ExistingNodeNumberAllocator, build_existing_node_number_allocator
from infrahub.pools.scope import AllocationScopeResolver
from infrahub.profiles.data_reader import ProfileDataReader
from infrahub.profiles.node_applier import NodeProfilesApplier
from tests.helpers.number_pool import (
    SCOPED_ATTRIBUTE_NAME,
    SCOPED_DEVICE,
    SCOPED_POOL_SCHEMA,
    save_schema_kinds,
    scoped_device_holding,
    scoped_pool,
    scoped_site,
)

if TYPE_CHECKING:
    from collections.abc import Generator

    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase
    from infrahub.pools.scope import Division


# Two scalar scope elements, so two divisions can hold different values that join into the same dotted key.
SCOPED_ROUTER = NodeSchema(
    name="Router",
    namespace="Scope",
    label="Router",
    human_friendly_id=["name__value"],
    attributes=[
        AttributeSchema(name="name", kind="Text", unique=True),
        AttributeSchema(name=SCOPED_ATTRIBUTE_NAME, kind="Number", optional=True),
        AttributeSchema(name="role", kind="Text", optional=False),
        AttributeSchema(name="row", kind="Text", optional=False),
    ],
)


async def unnumbered_device(db: InfrahubDatabase, branch: Branch, name: str, site: Node) -> Node:
    device = await Node.init(db=db, schema=SCOPED_DEVICE.kind, branch=branch)
    await device.new(db=db, name=name, role="leaf", tags=["red"], site=site)
    await device.save(db=db)
    return device


async def unnumbered_router(db: InfrahubDatabase, branch: Branch, name: str, role: str, row: str) -> Node:
    router = await Node.init(db=db, schema=SCOPED_ROUTER.kind, branch=branch)
    await router.new(db=db, name=name, role=role, row=row)
    await router.save(db=db)
    return router


async def allocate_existing(
    db: InfrahubDatabase, branch: Branch, pool: CoreNumberPool, devices: list[Node], kind: str = SCOPED_DEVICE.kind
) -> None:
    """Allocate the `vlan_id` of the nodes in the given order."""
    allocator = build_existing_node_number_allocator(db=db, branch=branch)
    attribute = registry.schema.get(name=kind, branch=branch, duplicate=False).get_attribute(name=SCOPED_ATTRIBUTE_NAME)
    await allocator.allocate(
        pool=pool,
        attribute=attribute,
        kind=kind,
        node_ids=[device.id for device in devices],
        branch=branch,
        at=Timestamp(),
        user_id=SYSTEM_USER_ID,
    )


async def stored_vlan_ids(db: InfrahubDatabase, branch: Branch, devices: list[Node]) -> dict[str, int | None]:
    loaded = await NodeManager.get_many(db=db, branch=branch, ids=[device.id for device in devices])
    return {
        str(node.get_attribute("name").value): node.get_attribute(SCOPED_ATTRIBUTE_NAME).value
        for node in loaded.values()
    }


class SiteReadRecordingDivisionReader:
    """Records, for each node whose division is read, whether the node's `site` peers were already loaded."""

    def __init__(self, reader: NodeNumberPoolDivisionReader) -> None:
        self.reader = reader
        self.site_loaded: list[bool] = []

    def scope_field_names(self, pool: Node, kind: str, attribute_name: str) -> list[str]:
        return self.reader.scope_field_names(pool=pool, kind=kind, attribute_name=attribute_name)

    async def read_for_pool(self, node: Node, pool: Node, attribute_name: str) -> Division | None:
        self.site_loaded.append(node.get_relationship("site").has_fetched_relationships)
        return await self.reader.read_for_pool(node=node, pool=pool, attribute_name=attribute_name)


def migration_exhaustion_pattern(pool: CoreNumberPool, description: str, count: int, kind: str, size: int) -> str:
    text = (
        f"Pool {pool.get_attribute('name').value} ({pool.id}) has no free number left in its ranges for {description}:"
        f" {count} node(s) of {kind} being filled are in this division and the ranges hold {size} number(s)."
    )
    return f"^{re.escape(text)}$"


class TestExistingNodeNumbers:
    """Each test numbers its own pool, sites and nodes, so no division is shared between tests."""

    @pytest.fixture(scope="class")
    def number_pool_node_class(self, default_branch_scope_class: Branch) -> Generator[None]:
        previous = registry.node.get(InfrahubKind.NUMBERPOOL)
        registry.node[InfrahubKind.NUMBERPOOL] = CoreNumberPool
        yield
        if previous is None:
            registry.node.pop(InfrahubKind.NUMBERPOOL, None)
        else:
            registry.node[InfrahubKind.NUMBERPOOL] = previous

    @pytest.fixture(scope="class")
    async def scoped_schema(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        register_core_models_schema_scope_class: SchemaBranch,
        number_pool_node_class: None,
    ) -> None:
        """The scoped pool test schema, saved on the default branch so that its fields hold the ids a scope stores."""
        await save_schema_kinds(
            db=db,
            schema=SchemaRoot(generics=SCOPED_POOL_SCHEMA.generics, nodes=[*SCOPED_POOL_SCHEMA.nodes, SCOPED_ROUTER]),
        )

    async def test_node_with_a_reservation_in_its_site_keeps_the_reserved_number(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, scoped_schema: None
    ) -> None:
        branch = default_branch_scope_class
        pool = await scoped_pool(db=db, name="vlan-per-site-with-reservation", allocation_scope=["site"])
        site = await scoped_site(db=db, branch=branch, name="reservation-site")
        devices = [
            await unnumbered_device(db=db, branch=branch, name="reservation-device-1", site=site),
            await scoped_device_holding(
                db=db, branch=branch, pool=pool, name="reservation-device-7", site=site, number=7
            ),
        ]

        await allocate_existing(db=db, branch=branch, pool=pool, devices=devices)

        assert await stored_vlan_ids(db=db, branch=branch, devices=devices) == {
            "reservation-device-1": 1,
            "reservation-device-7": 7,
        }
        await verify_graph(db=db)

    async def test_scope_values_set_by_a_profile_place_the_node_in_the_division_they_give(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, scoped_schema: None
    ) -> None:
        """The device that takes its site and role from a profile shares the division of a device that sets them."""
        branch = default_branch_scope_class
        pool = await scoped_pool(db=db, name="vlan-per-site-and-role", allocation_scope=["site", "role"])
        site_a = await scoped_site(db=db, branch=branch, name="profile-site-a")
        site_b = await scoped_site(db=db, branch=branch, name="profile-site-b")
        profile = await Node.init(db=db, schema=f"Profile{SCOPED_DEVICE.kind}", branch=branch)
        await profile.new(db=db, profile_name="site-a-spine", profile_priority=1000, site=site_a, role="spine")
        await profile.save(db=db)
        leaf = await Node.init(db=db, schema=SCOPED_DEVICE.kind, branch=branch)
        await leaf.new(db=db, name="device-a-leaf", role="leaf", tags=["red"], site=site_a)
        await leaf.save(db=db)
        from_profile = await create_node(
            data={"name": {"value": "device-a-spine-from-profile"}, "tags": {"value": ["red"]}, "profiles": [profile]},
            db=db,
            branch=branch,
            schema=db.schema.get(name=SCOPED_DEVICE.kind, branch=branch, duplicate=False),
        )
        spine = await Node.init(db=db, schema=SCOPED_DEVICE.kind, branch=branch)
        await spine.new(db=db, name="device-a-spine", role="spine", tags=["red"], site=site_a)
        await spine.save(db=db)
        other_site_spine = await Node.init(db=db, schema=SCOPED_DEVICE.kind, branch=branch)
        await other_site_spine.new(db=db, name="device-b-spine", role="spine", tags=["red"], site=site_b)
        await other_site_spine.save(db=db)
        devices = [leaf, from_profile, spine, other_site_spine]
        stored = await NodeManager.get_one(db=db, branch=branch, id=from_profile.id, raise_on_error=True)
        assert stored.get_attribute("role").is_from_profile is True
        assert (await stored.get_relationship("site").get_relationships(db=db))[0].is_from_profile is True

        await allocate_existing(db=db, branch=branch, pool=pool, devices=devices)

        assert await stored_vlan_ids(db=db, branch=branch, devices=devices) == {
            "device-a-leaf": 1,
            "device-a-spine-from-profile": 1,
            "device-a-spine": 2,
            "device-b-spine": 1,
        }
        await verify_graph(db=db)

    async def test_site_scope_reads_the_sites_of_all_nodes_when_loading_them(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, scoped_schema: None
    ) -> None:
        branch = default_branch_scope_class
        pool = await scoped_pool(db=db, name="vlan-per-site-loaded", allocation_scope=["site"])
        site = await scoped_site(db=db, branch=branch, name="loaded-site")
        devices = [
            await unnumbered_device(db=db, branch=branch, name=f"loaded-device-{index}", site=site)
            for index in range(1, 4)
        ]
        recorder = SiteReadRecordingDivisionReader(
            reader=NodeNumberPoolDivisionReader(
                db=db,
                scope_resolver=AllocationScopeResolver(
                    schema_branch=registry.schema.get_schema_branch(name=branch.name)
                ),
                profiles_applier=NodeProfilesApplier(
                    db=db, branch=branch, profile_data_reader=ProfileDataReader(db=db, branch=branch)
                ),
            )
        )
        allocator = ExistingNodeNumberAllocator(db=db, division_reader=recorder, node_manager=NodeManager)

        await allocator.allocate(
            pool=pool,
            attribute=registry.schema.get(name=SCOPED_DEVICE.kind, branch=branch, duplicate=False).get_attribute(
                name=SCOPED_ATTRIBUTE_NAME
            ),
            kind=SCOPED_DEVICE.kind,
            node_ids=[device.id for device in devices],
            branch=branch,
            at=Timestamp(),
            user_id=SYSTEM_USER_ID,
        )

        assert recorder.site_loaded == [True, True, True]
        assert await stored_vlan_ids(db=db, branch=branch, devices=devices) == {
            "loaded-device-1": 1,
            "loaded-device-2": 2,
            "loaded-device-3": 3,
        }

    async def test_full_site_names_the_site_its_node_count_and_the_range_size(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, scoped_schema: None
    ) -> None:
        branch = default_branch_scope_class
        pool = await scoped_pool(db=db, name="vlan-per-site-of-two", allocation_scope=["site"], start=1, end=2)
        full_site = await scoped_site(db=db, branch=branch, name="full-site")
        other_site = await scoped_site(db=db, branch=branch, name="full-other-site")
        devices = [await unnumbered_device(db=db, branch=branch, name="full-other-device-1", site=other_site)]
        devices += [
            await unnumbered_device(db=db, branch=branch, name=f"full-device-{index}", site=full_site)
            for index in range(1, 4)
        ]

        with pytest.raises(
            PoolExhaustedError,
            match=migration_exhaustion_pattern(
                pool=pool, description=f"site '{full_site.id}'", count=3, kind=SCOPED_DEVICE.kind, size=2
            ),
        ) as exc_info:
            await allocate_existing(db=db, branch=branch, pool=pool, devices=devices)

        assert isinstance(exc_info.value.__cause__, DivisionExhaustedError)

    async def test_divisions_sharing_a_key_are_counted_apart(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, scoped_schema: None
    ) -> None:
        """Both divisions join into the key `leaf.a.b`, but only the routers of the full one are counted."""
        branch = default_branch_scope_class
        pool = await scoped_pool(
            db=db, name="vlan-per-role-row", allocation_scope=["role", "row"], kind=SCOPED_ROUTER.kind, start=1, end=1
        )
        routers = [await unnumbered_router(db=db, branch=branch, name="router-other-1", role="leaf", row="a.b")]
        routers += [
            await unnumbered_router(db=db, branch=branch, name=f"router-full-{index}", role="leaf.a", row="b")
            for index in range(1, 3)
        ]

        with pytest.raises(
            PoolExhaustedError,
            match=migration_exhaustion_pattern(
                pool=pool, description="role 'leaf.a', row 'b'", count=2, kind=SCOPED_ROUTER.kind, size=1
            ),
        ):
            await allocate_existing(db=db, branch=branch, pool=pool, devices=routers, kind=SCOPED_ROUTER.kind)
