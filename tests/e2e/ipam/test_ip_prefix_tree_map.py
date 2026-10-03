"""Tree Map tab on an IP prefix detail page.

Opens the seeded 10.0.0.0/8 supernet, switches to the Tree Map tab and checks the
allocated /16 tiles, the first free block and the legend. The drill-down scenario clicks a
child tile and checks the child's own Tree Map opens with the namespace query param kept.
The branch scenario creates a child prefix on a throwaway branch and checks it shows up
only when that branch is selected. The create scenario allocates a free block from its
tile on a throwaway branch and checks the map refreshes in place; a read-only user sees
the free tile disabled. The address-prefix scenario opens the seeded 10.0.0.0/16, whose
members are IP addresses, and checks the Tree Map tab shows the empty state with the
utilisation meter and a link to the IP Addresses tab, both when opened from the IPAM tree
and when reached by drilling down from the supernet's map.
"""

from __future__ import annotations

import contextlib
import re
from typing import TYPE_CHECKING

import pytest
from helpers import generate_random_branch_name
from playwright.async_api import expect

pytestmark = pytest.mark.shard_foundation

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from data.handles import IpamPoolsHandle
    from helpers import BranchAPI
    from infrahub_sdk import InfrahubClient
    from playwright.async_api import Page

SUPERNET = "10.0.0.0/8"
ADDRESS_PREFIX = "10.0.0.0/16"
BRANCH_ONLY_CHILD = "10.5.0.0/16"
FIRST_FREE_BLOCK = "10.3.0.0/16"
FIRST_FREE_BLOCK_ALLOCATED_TILE = re.compile(r"^10\.3\.0\.0\/16, ")


async def open_tree_map(page: Page) -> None:
    await page.goto("/ipam")
    await page.get_by_test_id("identifier-cell").get_by_role("link", name=SUPERNET).click()
    await page.get_by_role("link", name="Tree Map").click()
    await expect(page.get_by_test_id("ip-prefix-tree-map")).to_be_visible()


class TestIpPrefixTreeMapView:
    async def test_shows_allocated_and_free_tiles(self, page: Page, data_ipam_pools: IpamPoolsHandle) -> None:
        await open_tree_map(page)

        tree_map = page.get_by_test_id("ip-prefix-tree-map")
        await expect(tree_map.get_by_role("link", name="10.0.0.0/16, 0% utilised")).to_be_visible()
        await expect(tree_map.get_by_role("link", name="10.1.0.0/16, 0% utilised")).to_be_visible()
        await expect(tree_map.get_by_role("link", name="10.2.0.0/16, 0% utilised")).to_be_visible()
        await expect(tree_map.get_by_role("button", name="10.3.0.0/16 available")).to_be_visible()

    async def test_shows_legend(self, page: Page, data_ipam_pools: IpamPoolsHandle) -> None:
        await open_tree_map(page)

        await expect(page.get_by_text("Allocated", exact=True)).to_be_visible()
        await expect(page.get_by_text("Free", exact=True)).to_be_visible()
        await expect(page.get_by_text("Smaller than 1/4096 of the prefix")).to_be_visible()


class TestIpPrefixTreeMapDrillDown:
    @pytest.fixture
    async def default_namespace_id(self, infrahub_client: InfrahubClient, data_ipam_pools: IpamPoolsHandle) -> str:
        namespace = await infrahub_client.get(kind="IpamNamespace", name__value="default")
        return namespace.id

    async def test_child_tile_opens_child_tree_map_in_same_namespace(
        self, page: Page, data_ipam_pools: IpamPoolsHandle, default_namespace_id: str
    ) -> None:
        supernet_id = data_ipam_pools.prefixes[SUPERNET]
        namespace_param = f"namespace={default_namespace_id}"
        await page.goto(f"/ipam/IpamIPPrefix/{supernet_id}/tree-map?{namespace_param}")
        tree_map = page.get_by_test_id("ip-prefix-tree-map")
        await expect(tree_map).to_be_visible()

        await tree_map.get_by_role("link", name="10.1.0.0/16, 0% utilised").click()

        await expect(page.get_by_role("heading", name="10.1.0.0/16")).to_be_visible()
        await expect(page.get_by_role("link", name="Tree Map")).to_have_attribute("aria-current", "page")
        await expect(page).to_have_url(re.compile(rf".*/tree-map\?.*{re.escape(namespace_param)}"))


class TestIpPrefixTreeMapBranch:
    @pytest.fixture
    async def branch(self, branch_api: BranchAPI, data_ipam_pools: IpamPoolsHandle) -> AsyncGenerator[str, None]:
        name = generate_random_branch_name("ip-prefix-tree-map-")
        await branch_api.create(name)
        yield name
        with contextlib.suppress(Exception):
            await branch_api.delete(name)

    @pytest.fixture
    async def supernet_id(self, infrahub_client: InfrahubClient, data_ipam_pools: IpamPoolsHandle) -> str:
        supernet = await infrahub_client.get(
            kind="IpamIPPrefix", prefix__value=SUPERNET, ip_namespace__name__value="default"
        )
        return supernet.id

    @pytest.fixture
    async def branch_only_child(self, infrahub_client: InfrahubClient, branch: str, supernet_id: str) -> str:
        child = await infrahub_client.create(
            kind="IpamIPPrefix",
            branch=branch,
            prefix=BRANCH_ONLY_CHILD,
            member_type="prefix",
            parent=supernet_id,
        )
        await child.save()
        return BRANCH_ONLY_CHILD

    async def test_branch_only_child_appears_on_its_branch_only(
        self, admin_page: Page, branch: str, supernet_id: str, branch_only_child: str
    ) -> None:
        tree_map_path = f"/ipam/IpamIPPrefix/{supernet_id}/tree-map"
        child_tile_name = f"{branch_only_child}, 0% utilised"

        # On the branch the new child is an allocated tile
        await admin_page.goto(f"{tree_map_path}?branch={branch}")
        tree_map = admin_page.get_by_test_id("ip-prefix-tree-map")
        await expect(tree_map).to_be_visible()
        await expect(tree_map.get_by_role("link", name=child_tile_name)).to_be_visible()

        # On the default branch the same block is still free
        await admin_page.goto(tree_map_path)
        tree_map = admin_page.get_by_test_id("ip-prefix-tree-map")
        await expect(tree_map.get_by_role("link", name="10.0.0.0/16, 0% utilised")).to_be_visible()
        await expect(tree_map.get_by_role("link", name=child_tile_name)).to_have_count(0)
        await expect(tree_map.get_by_role("button", name=f"{branch_only_child} available")).to_be_visible()


class TestIpPrefixTreeMapCreate:
    @pytest.fixture
    async def branch(self, branch_api: BranchAPI, data_ipam_pools: IpamPoolsHandle) -> AsyncGenerator[str, None]:
        name = generate_random_branch_name("ip-prefix-tree-map-create-")
        await branch_api.create(name)
        yield name
        with contextlib.suppress(Exception):
            await branch_api.delete(name)

    async def test_free_tile_creates_prefix_and_map_refreshes(
        self, admin_page: Page, branch: str, data_ipam_pools: IpamPoolsHandle
    ) -> None:
        supernet_id = data_ipam_pools.prefixes[SUPERNET]
        await admin_page.goto(f"/ipam/IpamIPPrefix/{supernet_id}/tree-map?branch={branch}")
        tree_map = admin_page.get_by_test_id("ip-prefix-tree-map")
        await expect(tree_map).to_be_visible()

        # The free tile opens the create form prefilled with its CIDR
        await tree_map.get_by_role("button", name=f"{FIRST_FREE_BLOCK} available").click()
        await expect(admin_page.get_by_label("Prefix *")).to_have_value(FIRST_FREE_BLOCK)
        await admin_page.get_by_role("button", name="Save").click()
        await expect(admin_page.get_by_text(f"IP Prefix {FIRST_FREE_BLOCK} created")).to_be_visible()
        await expect(admin_page.get_by_label("Prefix *")).not_to_be_visible()

        # The map refreshes in place: the block is now an allocated tile
        await expect(tree_map.get_by_role("link", name=FIRST_FREE_BLOCK_ALLOCATED_TILE)).to_be_visible()
        await expect(tree_map.get_by_role("button", name=f"{FIRST_FREE_BLOCK} available")).to_have_count(0)

    async def test_free_tile_is_disabled_for_read_only_user(
        self, read_only_page: Page, data_ipam_pools: IpamPoolsHandle
    ) -> None:
        supernet_id = data_ipam_pools.prefixes[SUPERNET]
        await read_only_page.goto(f"/ipam/IpamIPPrefix/{supernet_id}/tree-map")
        tree_map = read_only_page.get_by_test_id("ip-prefix-tree-map")
        await expect(tree_map).to_be_visible()

        await expect(tree_map.get_by_role("button", name=f"{FIRST_FREE_BLOCK} available")).to_be_disabled()


class TestIpPrefixTreeMapAddressPrefix:
    async def test_shows_empty_state_with_meter_and_link_to_addresses(
        self, page: Page, data_ipam_pools: IpamPoolsHandle
    ) -> None:
        await page.goto("/ipam")
        ipam_tree = page.get_by_role("treegrid", name="IPAM tree")
        await ipam_tree.get_by_role("button", name=f"Expand {SUPERNET}").click()
        await ipam_tree.get_by_text(ADDRESS_PREFIX).click()
        await expect(page.get_by_role("heading", name=ADDRESS_PREFIX)).to_be_visible()

        await page.get_by_role("link", name="Tree Map").click()

        empty_state = page.get_by_test_id("ip-prefix-tree-map-empty")
        await expect(empty_state).to_be_visible()
        await expect(empty_state.get_by_role("meter", name="Utilization")).to_be_visible()
        await expect(page.get_by_test_id("ip-prefix-tree-map")).to_have_count(0)

        await empty_state.get_by_role("link", name="IP Addresses").click()

        await expect(page).to_have_url(re.compile(r".*/ip_addresses(\?.*)?$"))
        await expect(page.get_by_test_id("ip-address-table")).to_be_visible()

    async def test_drill_down_into_address_prefix_shows_empty_state(
        self, page: Page, data_ipam_pools: IpamPoolsHandle
    ) -> None:
        supernet_id = data_ipam_pools.prefixes[SUPERNET]
        await page.goto(f"/ipam/IpamIPPrefix/{supernet_id}/tree-map")
        tree_map = page.get_by_test_id("ip-prefix-tree-map")
        await expect(tree_map).to_be_visible()

        await tree_map.get_by_role("link", name=f"{ADDRESS_PREFIX}, 0% utilised").click()

        await expect(page.get_by_role("heading", name=ADDRESS_PREFIX)).to_be_visible()
        await expect(page.get_by_role("link", name="Tree Map")).to_have_attribute("aria-current", "page")
        await expect(page.get_by_test_id("ip-prefix-tree-map-empty")).to_be_visible()
