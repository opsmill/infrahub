"""The IP pool details page: resource prefixes, allocations and the actions menu.

Depends on data_sites: the seeded "External prefixes pool" allocates one /29
per upstream and peering interface of every edge device (identifier
"<role>: <interface>.<device>"), the "Loopbacks pool" one /32 per device
(identifier = device name) and the "Internal networks pool" the three
10.x.0.0/16 prefixes without identifier. Every test reads the allocation
count it expects through the SDK, because the scenario-branch slice replays
two more /29 allocations on main when it is loaded in the same session.
"""

from __future__ import annotations

import contextlib
import re
from typing import TYPE_CHECKING

import pytest
from helpers import generate_random_branch_name, save_screenshot_for_docs
from playwright.async_api import expect

pytestmark = pytest.mark.shard_sites_a

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from data.handles import IpamPoolsHandle, SitesHandle
    from helpers import BranchAPI
    from infrahub_sdk import InfrahubClient
    from playwright.async_api import Locator, Page

EXTERNAL_POOL = "External prefixes pool"
EXTERNAL_PREFIX = "203.111.0.0/16"
LOOPBACKS_POOL = "Loopbacks pool"
LOOPBACKS_PREFIX = "10.0.0.0/16"
INTERNAL_POOL = "Internal networks pool"
EMPTY_PREFIX = "10.2.0.0/16"
EDGE_DEVICE = "atl1-edge1"

EXTERNAL_SLASH_29 = re.compile(r"^203\.111\.\d+\.\d+\/29$")
LOOPBACK_SLASH_32 = re.compile(r"^10\.0\.0\.\d+\/32$")


def pool_header(page: Page) -> Locator:
    return page.locator("header").filter(has=page.get_by_role("heading", level=1))


def allocations_grid(page: Page, title: str) -> Locator:
    return page.get_by_role("grid", name=title)


def allocations_title(page: Page, title: str) -> Locator:
    return page.get_by_role("heading", level=2, name=title).locator("..")


def allocation_count(count: int, title: str) -> re.Pattern[str]:
    return re.compile(rf"^\s*{re.escape(title)}\s*{count:,}\s*in ")


async def scroll_to_last_row(grid: Locator) -> None:
    """Bring the rows past the first viewport into the DOM: the grid renders only the visible ones."""
    await expect(grid.get_by_role("row").nth(1)).to_be_visible()
    await grid.evaluate("(grid) => { grid.scrollTop = grid.scrollHeight; }")


class TestIpPoolDetails:
    @pytest.fixture
    async def branch(self, branch_api: BranchAPI, data_sites: SitesHandle) -> AsyncGenerator[str, None]:
        name = generate_random_branch_name("ip-pool-")
        await branch_api.create(name)
        yield name
        with contextlib.suppress(Exception):
            await branch_api.delete(name)

    @pytest.fixture
    async def empty_pool_id(
        self, infrahub_client: InfrahubClient, data_ipam_pools: IpamPoolsHandle, data_sites: SitesHandle
    ) -> AsyncGenerator[str, None]:
        """A prefix pool of the test's own, since pools are branch-agnostic and an edit lands on every branch."""
        namespace = await infrahub_client.get(kind="IpamNamespace", name__value="default")
        pool = await infrahub_client.create(
            kind="CoreIPPrefixPool",
            name=generate_random_branch_name("ip pool e2e "),
            default_prefix_type="IpamIPPrefix",
            default_prefix_length=29,
            ip_namespace=namespace.id,
            resources=[data_ipam_pools.prefixes[EMPTY_PREFIX]],
        )
        await pool.save()
        yield pool.id
        with contextlib.suppress(Exception):
            await pool.delete()

    async def test_prefix_pool_on_default_branch(
        self,
        admin_page: Page,
        infrahub_client: InfrahubClient,
        data_ipam_pools: IpamPoolsHandle,
        data_sites: SitesHandle,
    ) -> None:
        resource_id = data_ipam_pools.prefixes[EXTERNAL_PREFIX]
        allocated_count = await infrahub_client.count(kind="IpamIPPrefix", parent__ids=[resource_id])

        await admin_page.goto(f"/resource-manager/{data_ipam_pools.pools[EXTERNAL_POOL]}")

        header = pool_header(admin_page)
        await expect(header.get_by_role("heading", level=1, name=EXTERNAL_POOL)).to_be_visible()
        await expect(header).to_contain_text("In namespace default")
        await expect(header).to_contain_text("Prefix kind defaults to IpamIPPrefix")
        await expect(header).to_contain_text("Prefix length defaults to /29")
        await expect(header).to_contain_text("Member type defaults to Address")

        resources = admin_page.get_by_role("listbox", name="Resource prefixes")
        await expect(resources.get_by_role("option")).to_have_count(1)
        await expect(resources.get_by_role("option", name=EXTERNAL_PREFIX)).to_have_attribute("aria-selected", "true")
        await expect(resources).not_to_contain_text("Weight")

        title = allocations_title(admin_page, "Allocated prefixes")
        await expect(title).to_have_text(allocation_count(allocated_count, "Allocated prefixes"))
        await expect(title).to_contain_text(f"in {EXTERNAL_PREFIX}")

        grid = allocations_grid(admin_page, "Allocated prefixes")
        await expect(grid.get_by_role("columnheader", name="Prefix")).to_be_visible()
        await expect(grid.get_by_role("columnheader", name="Identifier")).to_be_visible()
        await expect(grid.get_by_role("columnheader", name="Kind")).to_be_visible()

        edge_row = grid.get_by_role("row").filter(has_text=re.compile(rf"\.{EDGE_DEVICE}")).first
        await expect(edge_row.get_by_role("link", name=EXTERNAL_SLASH_29)).to_be_visible()
        await expect(edge_row).to_contain_text("IP Prefix")

    async def test_address_pool_on_default_branch(
        self, admin_page: Page, data_ipam_pools: IpamPoolsHandle, data_sites: SitesHandle
    ) -> None:
        await admin_page.goto(f"/resource-manager/{data_ipam_pools.pools[LOOPBACKS_POOL]}")

        header = pool_header(admin_page)
        await expect(header.get_by_role("heading", level=1, name=LOOPBACKS_POOL)).to_be_visible()
        await expect(header).to_contain_text("In namespace default")
        await expect(header).to_contain_text("Address kind defaults to IpamIPAddress")
        await expect(header).to_contain_text("Prefix length defaults to /32")

        resources = admin_page.get_by_role("listbox", name="Resource prefixes")
        await expect(resources.get_by_role("option", name=LOOPBACKS_PREFIX)).to_have_attribute("aria-selected", "true")

        await expect(allocations_title(admin_page, "Allocated addresses")).to_contain_text(f"in {LOOPBACKS_PREFIX}")
        grid = allocations_grid(admin_page, "Allocated addresses")
        await expect(grid.get_by_role("columnheader", name="Address")).to_be_visible()

        loopback = data_sites.loopback_ips[EDGE_DEVICE]
        assert LOOPBACK_SLASH_32.match(loopback)
        edge_row = grid.get_by_role("row").filter(has_text=EDGE_DEVICE)
        await expect(edge_row.get_by_role("link", name=loopback, exact=True)).to_be_visible()
        await expect(edge_row).to_contain_text("IP Address")
        await save_screenshot_for_docs(admin_page, "tutorial_resource_manager_loopbacks_pool")

        await edge_row.get_by_role("link", name=loopback, exact=True).click()
        await expect(admin_page).to_have_url(re.compile(r"/ipam/IpamIPAddress/"))

    async def test_allocations_without_identifier_show_none(
        self, admin_page: Page, data_ipam_pools: IpamPoolsHandle, data_sites: SitesHandle
    ) -> None:
        await admin_page.goto(f"/resource-manager/{data_ipam_pools.pools[INTERNAL_POOL]}")

        header = pool_header(admin_page)
        await expect(header).to_contain_text("Prefix length defaults to /16")
        await expect(header).to_contain_text("Member type defaults to Prefix")

        grid = allocations_grid(admin_page, "Allocated prefixes")
        for prefix in ("10.0.0.0/16", "10.1.0.0/16", "10.2.0.0/16"):
            row = grid.get_by_role("row").filter(has=admin_page.get_by_role("link", name=prefix, exact=True))
            await expect(row).to_contain_text("None")
            await expect(row).to_contain_text("IP Prefix")

    async def test_link_with_a_resource_prefix(
        self, admin_page: Page, data_ipam_pools: IpamPoolsHandle, data_sites: SitesHandle
    ) -> None:
        pool_id = data_ipam_pools.pools[EXTERNAL_POOL]
        resource_id = data_ipam_pools.prefixes[EXTERNAL_PREFIX]

        await admin_page.goto(f"/resource-manager/{pool_id}/resources/{resource_id}")
        resources = admin_page.get_by_role("listbox", name="Resource prefixes")
        await expect(resources.get_by_role("option", name=EXTERNAL_PREFIX)).to_have_attribute("aria-selected", "true")
        await expect(allocations_title(admin_page, "Allocated prefixes")).to_contain_text(f"in {EXTERNAL_PREFIX}")

        # a resource prefix the pool does not have
        await admin_page.goto(f"/resource-manager/{pool_id}/resources/not-a-resource-of-this-pool")
        await expect(admin_page.get_by_text("Resource prefix not found")).to_be_visible()
        await expect(resources.get_by_role("option", name=EXTERNAL_PREFIX)).not_to_have_attribute(
            "aria-selected", "true"
        )
        await admin_page.get_by_role("link", name="View the pool").click()
        await expect(admin_page).to_have_url(re.compile(rf"/resource-manager/{pool_id}$"))
        await expect(resources.get_by_role("option", name=EXTERNAL_PREFIX)).to_have_attribute("aria-selected", "true")

    async def test_resource_prefix_without_allocation(self, admin_page: Page, empty_pool_id: str) -> None:
        await admin_page.goto(f"/resource-manager/{empty_pool_id}")

        header = pool_header(admin_page)
        await expect(header).to_contain_text("Prefix kind defaults to IpamIPPrefix")
        await expect(header).to_contain_text("Prefix length defaults to /29")
        await expect(header).to_contain_text("Member type defaults to Prefix")

        resources = admin_page.get_by_role("listbox", name="Resource prefixes")
        await expect(resources.get_by_role("option", name=EMPTY_PREFIX)).to_contain_text("0%")
        await expect(allocations_title(admin_page, "Allocated prefixes")).to_have_text(
            allocation_count(0, "Allocated prefixes")
        )
        await expect(admin_page.get_by_text(f"No prefixes in {EMPTY_PREFIX} yet")).to_be_visible()

    async def test_prefix_allocated_on_a_branch(
        self,
        admin_page: Page,
        branch: str,
        infrahub_client: InfrahubClient,
        data_ipam_pools: IpamPoolsHandle,
    ) -> None:
        pool_id = data_ipam_pools.pools[EXTERNAL_POOL]
        resource_id = data_ipam_pools.prefixes[EXTERNAL_PREFIX]
        identifier = f"ip-pool-e2e-{branch}"
        main_count = await infrahub_client.count(kind="IpamIPPrefix", parent__ids=[resource_id])
        pool = await infrahub_client.get(kind="CoreIPPrefixPool", id=pool_id)
        await infrahub_client.allocate_next_ip_prefix(resource_pool=pool, identifier=identifier, branch=branch)

        # the branch view counts the main allocations plus its own
        await admin_page.goto(f"/resource-manager/{pool_id}?branch={branch}")
        await expect(allocations_title(admin_page, "Allocated prefixes")).to_have_text(
            allocation_count(main_count + 1, "Allocated prefixes")
        )
        grid = allocations_grid(admin_page, "Allocated prefixes")
        await scroll_to_last_row(grid)
        branch_row = grid.get_by_role("row").filter(has_text=identifier)
        await expect(branch_row.get_by_role("link", name=EXTERNAL_SLASH_29)).to_be_visible()

        # the default branch does not have it
        await admin_page.goto(f"/resource-manager/{pool_id}")
        await expect(allocations_title(admin_page, "Allocated prefixes")).to_have_text(
            allocation_count(main_count, "Allocated prefixes")
        )
        await scroll_to_last_row(grid)
        await expect(grid.get_by_role("row").filter(has_text=identifier)).to_have_count(0)

    async def test_address_allocated_on_a_branch(
        self,
        admin_page: Page,
        branch: str,
        infrahub_client: InfrahubClient,
        data_ipam_pools: IpamPoolsHandle,
    ) -> None:
        pool_id = data_ipam_pools.pools[LOOPBACKS_POOL]
        resource_id = data_ipam_pools.prefixes[LOOPBACKS_PREFIX]
        identifier = f"ip-pool-e2e-{branch}"
        main_count = await infrahub_client.count(kind="IpamIPAddress", ip_prefix__ids=[resource_id])
        pool = await infrahub_client.get(kind="CoreIPAddressPool", id=pool_id)
        await infrahub_client.allocate_next_ip_address(resource_pool=pool, identifier=identifier, branch=branch)

        await admin_page.goto(f"/resource-manager/{pool_id}?branch={branch}")
        await expect(allocations_title(admin_page, "Allocated addresses")).to_have_text(
            allocation_count(main_count + 1, "Allocated addresses")
        )
        grid = allocations_grid(admin_page, "Allocated addresses")
        await scroll_to_last_row(grid)
        branch_row = grid.get_by_role("row").filter(has_text=identifier)
        await expect(branch_row.get_by_role("link", name=LOOPBACK_SLASH_32)).to_be_visible()

        await admin_page.goto(f"/resource-manager/{pool_id}")
        await expect(allocations_title(admin_page, "Allocated addresses")).to_have_text(
            allocation_count(main_count, "Allocated addresses")
        )
        await scroll_to_last_row(grid)
        await expect(grid.get_by_role("row").filter(has_text=identifier)).to_have_count(0)

    async def test_edit_pool_from_actions_menu(self, admin_page: Page, branch: str, empty_pool_id: str) -> None:
        await admin_page.goto(f"/resource-manager/{empty_pool_id}?branch={branch}")

        header = pool_header(admin_page)
        await header.get_by_role("button", name="Actions").click()
        await admin_page.get_by_role("menuitem", name="Edit").click()
        await admin_page.get_by_label("Description").fill("edited from the details page")
        await admin_page.get_by_role("button", name="Save").click()

        await expect(admin_page.get_by_text("IPPrefixPool updated")).to_be_visible()
        await expect(header.get_by_text("edited from the details page")).to_be_visible()

    async def test_read_only_user_cannot_manage_pool(
        self, read_only_page: Page, data_ipam_pools: IpamPoolsHandle, data_sites: SitesHandle
    ) -> None:
        await read_only_page.goto(f"/resource-manager/{data_ipam_pools.pools[EXTERNAL_POOL]}")

        header = pool_header(read_only_page)
        await expect(header.get_by_role("heading", level=1, name=EXTERNAL_POOL)).to_be_visible()
        await header.get_by_role("button", name="Actions").click()
        await expect(read_only_page.get_by_role("menuitem", name="Copy ID")).to_be_visible()
        await expect(read_only_page.get_by_role("menuitem", name="Edit")).to_have_attribute("aria-disabled", "true")
        await expect(read_only_page.get_by_role("menuitem", name="Groups")).to_have_attribute("aria-disabled", "true")
        await expect(read_only_page.get_by_role("menuitem", name="Delete")).to_have_attribute("aria-disabled", "true")
