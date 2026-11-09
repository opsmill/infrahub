"""Port of frontend/app/tests/e2e/ipam/ip-prefix-create-with-pool.spec.ts.

Allocate an IP prefix from the seeded "External prefixes pool". Depends on
data_scenario_branches (the full dataset): the asserted next-free prefix
(203.111.0.248/29) assumes the 30 site /29s plus the dropped-scenario ballast
/29 that slice replays — with sites alone the next-free would be .240/29.
"""

from __future__ import annotations

import contextlib
import re
from typing import TYPE_CHECKING

import pytest
from helpers import generate_random_branch_name, select_pool
from playwright.async_api import expect

pytestmark = pytest.mark.shard_branches_repo

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from data.handles import ScenarioBranchesHandle
    from helpers import BranchAPI
    from playwright.async_api import Page


class TestAllocateIpPrefixWithPool:
    @pytest.fixture
    async def branch(
        self, branch_api: BranchAPI, data_scenario_branches: ScenarioBranchesHandle
    ) -> AsyncGenerator[str, None]:
        name = generate_random_branch_name("ip-prefix-pool-")
        await branch_api.create(name)
        yield name
        with contextlib.suppress(Exception):
            await branch_api.delete(name)

    async def test_create_an_ip_prefix_using_a_pool(self, admin_page: Page, branch: str) -> None:
        await admin_page.goto(f"/ipam?branch={branch}")
        await admin_page.get_by_test_id("create-object-button").click()

        await select_pool(admin_page, "External prefixes pool")
        await expect(admin_page.get_by_label("Prefix *")).to_contain_text("Allocated by pool")
        await expect(admin_page.get_by_test_id("source-pool-badge")).to_contain_text("External prefixes pool")
        await admin_page.get_by_role("textbox", name="Description").fill("prefix from pool")
        await admin_page.get_by_role("button", name="Save").click()

        await expect(admin_page.get_by_text("IP Prefix 203.111.0.248/29 created")).to_be_visible()
        await (
            admin_page.get_by_test_id("object-list-search-bar")
            .get_by_role("searchbox", name="Search")
            .fill("203.111.0.248/29")
        )
        await expect(admin_page.get_by_text("prefix from pool")).to_be_visible()

    async def test_create_an_ip_prefix_using_a_pool_with_a_custom_prefix_length(
        self, admin_page: Page, branch: str
    ) -> None:
        await admin_page.goto(f"/ipam?branch={branch}")
        await admin_page.get_by_test_id("create-object-button").click()

        await select_pool(admin_page, "External prefixes pool")
        await expect(admin_page.get_by_label("Prefix *")).to_contain_text("Allocated by pool")

        # The pool's default prefix length is surfaced as a placeholder.
        await expect(admin_page.get_by_test_id("pool-prefix-length-input")).to_have_attribute("placeholder", "29")

        # Override the pool's default prefix length (/29) with a smaller subnet size.
        await admin_page.get_by_test_id("pool-prefix-length-input").fill("30")
        await admin_page.get_by_role("textbox", name="Description").fill("prefix from pool with custom size")
        await admin_page.get_by_role("button", name="Save").click()

        # The allocation honours the typed prefix length rather than the pool default.
        await expect(admin_page.get_by_text(re.compile(r"IP Prefix 203\.111\.\d+\.\d+/30 created"))).to_be_visible()
