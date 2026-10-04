"""Tree Map tab on an IP prefix detail page: tiles, drill-down, create, empty state and IPv6."""

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
PREFIX_CHILD = "10.1.0.0/16"
EMPTY_PREFIX_CHILD = "10.2.0.0/16"
BRANCH_ONLY_CHILD = "10.5.0.0/16"
FIRST_FREE_BLOCK = "10.3.0.0/16"
IPV6_SUPERNET = "2001:db8::/100"
IPV6_CHILD_TILE = re.compile(r"^2001:db8::")
FREE_TILE = re.compile(r" available$")


def allocated_tile(prefix: str) -> re.Pattern[str]:
    """Match an allocated tile by its CIDR regardless of the utilization it reports."""
    return re.compile(rf"^{re.escape(prefix)}, ")


@pytest.fixture
async def supernet_id(infrahub_client: InfrahubClient, data_ipam_pools: IpamPoolsHandle) -> str:
    supernet = await infrahub_client.get(
        kind="IpamIPPrefix", prefix__value=SUPERNET, ip_namespace__name__value="default"
    )
    return supernet.id


@pytest.fixture
async def branch(branch_api: BranchAPI, data_ipam_pools: IpamPoolsHandle) -> AsyncGenerator[str, None]:
    name = generate_random_branch_name("ip-prefix-tree-map-")
    await branch_api.create(name)
    yield name
    with contextlib.suppress(Exception):
        await branch_api.delete(name)


async def open_tree_map(page: Page) -> None:
    await page.goto("/ipam")
    await page.get_by_test_id("identifier-cell").get_by_role("link", name=SUPERNET).click()
    await page.get_by_role("link", name="Tree Map").click()
    await expect(page.get_by_test_id("ip-prefix-tree-map")).to_be_visible()


class TestIpPrefixTreeMapView:
    async def test_shows_allocated_and_free_tiles(self, page: Page, data_ipam_pools: IpamPoolsHandle) -> None:
        await open_tree_map(page)

        tree_map = page.get_by_test_id("ip-prefix-tree-map")
        await expect(tree_map.get_by_role("link", name=allocated_tile(ADDRESS_PREFIX))).to_be_visible()
        await expect(tree_map.get_by_role("link", name=allocated_tile(PREFIX_CHILD))).to_be_visible()
        await expect(tree_map.get_by_role("link", name=allocated_tile(EMPTY_PREFIX_CHILD))).to_be_visible()
        await expect(tree_map.get_by_role("button", name=f"{FIRST_FREE_BLOCK} available")).to_be_visible()

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
        self, page: Page, supernet_id: str, default_namespace_id: str
    ) -> None:
        namespace_param = f"namespace={default_namespace_id}"
        await page.goto(f"/ipam/IpamIPPrefix/{supernet_id}/tree-map?{namespace_param}")
        tree_map = page.get_by_test_id("ip-prefix-tree-map")
        await expect(tree_map).to_be_visible()

        await tree_map.get_by_role("link", name=allocated_tile(PREFIX_CHILD)).click()

        await expect(page.get_by_role("heading", name=PREFIX_CHILD)).to_be_visible()
        await expect(page.get_by_role("link", name="Tree Map")).to_have_attribute("aria-current", "page")
        await expect(page).to_have_url(re.compile(rf".*/tree-map\?.*{re.escape(namespace_param)}"))

        ipam_tree = page.get_by_role("treegrid", name="IPAM tree")
        await expect(ipam_tree.get_by_role("row", name=re.compile(rf"^{re.escape(PREFIX_CHILD)}"))).to_contain_class(
            "bg-selected"
        )


class TestIpPrefixTreeMapBranch:
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
        child_tile = allocated_tile(branch_only_child)

        await admin_page.goto(f"{tree_map_path}?branch={branch}")
        tree_map = admin_page.get_by_test_id("ip-prefix-tree-map")
        await expect(tree_map).to_be_visible()
        await expect(tree_map.get_by_role("link", name=child_tile)).to_be_visible()

        await admin_page.goto(tree_map_path)
        tree_map = admin_page.get_by_test_id("ip-prefix-tree-map")
        await expect(tree_map.get_by_role("link", name=allocated_tile(ADDRESS_PREFIX))).to_be_visible()
        await expect(tree_map.get_by_role("link", name=child_tile)).to_have_count(0)
        await expect(tree_map.get_by_role("button", name=f"{branch_only_child} available")).to_be_visible()


class TestIpPrefixTreeMapCreate:
    async def test_free_tile_creates_prefix_and_map_refreshes(
        self, admin_page: Page, branch: str, supernet_id: str
    ) -> None:
        await admin_page.goto(f"/ipam/IpamIPPrefix/{supernet_id}/tree-map?branch={branch}")
        tree_map = admin_page.get_by_test_id("ip-prefix-tree-map")
        await expect(tree_map).to_be_visible()

        await tree_map.get_by_role("button", name=f"{FIRST_FREE_BLOCK} available").click()
        await expect(admin_page.get_by_label("Prefix *")).to_have_value(FIRST_FREE_BLOCK)
        await admin_page.get_by_role("button", name="Save").click()
        await expect(admin_page.get_by_text(f"IP Prefix {FIRST_FREE_BLOCK} created")).to_be_visible()
        await expect(admin_page.get_by_label("Prefix *")).not_to_be_visible()

        await expect(tree_map.get_by_role("link", name=allocated_tile(FIRST_FREE_BLOCK))).to_be_visible()
        await expect(tree_map.get_by_role("button", name=f"{FIRST_FREE_BLOCK} available")).to_have_count(0)

    async def test_free_tile_is_disabled_for_read_only_user(self, read_only_page: Page, supernet_id: str) -> None:
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

    async def test_drill_down_into_address_prefix_shows_empty_state(self, page: Page, supernet_id: str) -> None:
        await page.goto(f"/ipam/IpamIPPrefix/{supernet_id}/tree-map")
        tree_map = page.get_by_test_id("ip-prefix-tree-map")
        await expect(tree_map).to_be_visible()

        await tree_map.get_by_role("link", name=allocated_tile(ADDRESS_PREFIX)).click()

        await expect(page.get_by_role("heading", name=ADDRESS_PREFIX)).to_be_visible()
        await expect(page.get_by_role("link", name="Tree Map")).to_have_attribute("aria-current", "page")
        await expect(page.get_by_test_id("ip-prefix-tree-map-empty")).to_be_visible()


class TestIpPrefixTreeMapIpv6:
    async def test_shows_ipv6_children_and_free_blocks_without_page_errors(
        self, page: Page, data_ipam_pools: IpamPoolsHandle
    ) -> None:
        page_errors: list[str] = []
        page.on("pageerror", lambda error: page_errors.append(str(error)))

        await page.goto("/ipam")
        await page.get_by_role("treegrid", name="IPAM tree").get_by_text(IPV6_SUPERNET).click()
        await expect(page.get_by_role("heading", name=IPV6_SUPERNET)).to_be_visible()

        await page.get_by_role("link", name="Tree Map").click()

        tree_map = page.get_by_test_id("ip-prefix-tree-map")
        await expect(tree_map).to_be_visible()
        await expect(tree_map.get_by_role("link", name=IPV6_CHILD_TILE)).to_have_count(6)
        await expect(tree_map.get_by_role("button", name=FREE_TILE).first).to_be_visible()
        assert not page_errors
