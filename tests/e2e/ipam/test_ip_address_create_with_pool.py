"""Port of frontend/app/tests/e2e/ipam/ip-address-create-with-pool.spec.ts.

Allocate an IP address from the seeded "Management addresses pool". Depends on
data_sites: the asserted next-free address (172.16.0.31/16) assumes exactly the
30 device management addresses are already consumed.
"""

from __future__ import annotations

import contextlib
import re
from typing import TYPE_CHECKING

import pytest
from helpers import generate_random_branch_name
from playwright.async_api import expect

pytestmark = pytest.mark.shard_sites_b

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from data.handles import SitesHandle
    from helpers import BranchAPI
    from playwright.async_api import Page


class TestAllocateIpAddressWithPool:
    @pytest.fixture
    async def branch(self, branch_api: BranchAPI, data_sites: SitesHandle) -> AsyncGenerator[str, None]:
        name = generate_random_branch_name("ip-address-pool-")
        await branch_api.create(name)
        yield name
        with contextlib.suppress(Exception):
            await branch_api.delete(name)

    async def test_create_an_ip_address_using_a_pool(self, admin_page: Page, branch: str) -> None:
        await admin_page.goto(f"/ipam/ip_addresses?branch={branch}")
        await admin_page.get_by_test_id("create-object-button").click()

        await admin_page.get_by_test_id("select-open-pool-option-button").click()
        await admin_page.get_by_role("option", name="Management addresses pool").click()
        await expect(admin_page.get_by_label("Address *")).to_contain_text("Allocated by pool")
        await expect(admin_page.get_by_test_id("source-pool-badge")).to_contain_text("Management addresses pool")
        await admin_page.get_by_label("Description").fill("address from pool")
        await admin_page.get_by_role("button", name="Save").click()

        await expect(admin_page.get_by_text("IP Address 172.16.0.31/16 created")).to_be_visible()
        await (
            admin_page.get_by_test_id("object-list-search-bar")
            .get_by_role("searchbox", name="Search")
            .fill("172.16.0.31/16")
        )
        await expect(admin_page.get_by_text("address from pool")).to_be_visible()

    async def test_create_an_ip_address_using_a_pool_with_a_custom_prefix_length(
        self, admin_page: Page, branch: str
    ) -> None:
        await admin_page.goto(f"/ipam/ip_addresses?branch={branch}")
        await admin_page.get_by_test_id("create-object-button").click()

        await admin_page.get_by_test_id("select-open-pool-option-button").click()
        await admin_page.get_by_role("option", name="Management addresses pool").click()
        await expect(admin_page.get_by_label("Address *")).to_contain_text("Allocated by pool")

        # The pool's default prefix length is surfaced as a placeholder.
        await expect(admin_page.get_by_test_id("pool-prefix-length-input")).to_have_attribute("placeholder", "16")

        # Override the pool's default prefix length (/16) with a custom mask.
        await admin_page.get_by_test_id("pool-prefix-length-input").fill("24")
        await admin_page.get_by_label("Description").fill("address from pool with custom prefix")
        await admin_page.get_by_role("button", name="Save").click()

        # The allocation honours the typed prefix length rather than the pool default.
        await expect(admin_page.get_by_text(re.compile(r"IP Address 172\.16\.0\.\d+/24 created"))).to_be_visible()
