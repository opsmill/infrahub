"""Port of frontend/app/tests/e2e/ipam/ip-prefix-create-with-pool.spec.ts.

Allocate an IP prefix from the seeded "External prefixes pool". Depends on
data_scenario_branches (the full dataset): the asserted next-free prefix
(203.111.0.96/29) assumes the 12 site /29s (2 kept sites x 6 upstream/peering
allocations each). The dropped-scenario pool ballast was removed with the
2-site slim (see data/scenario_branches.py).
"""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING

import pytest
from helpers import generate_random_branch_name
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

        await admin_page.get_by_test_id("select-open-pool-option-button").click()
        await admin_page.get_by_role("option", name="External prefixes pool").click()
        await expect(admin_page.get_by_label("Prefix *")).to_contain_text("Allocated by pool")
        await expect(admin_page.get_by_test_id("source-pool-badge")).to_contain_text("External prefixes pool")
        await admin_page.get_by_role("textbox", name="Description").fill("prefix from pool")
        await admin_page.get_by_role("button", name="Save").click()

        await expect(admin_page.get_by_text("IP Prefix 203.111.0.96/29 created")).to_be_visible()
        await (
            admin_page.get_by_test_id("object-list-search-bar")
            .get_by_role("searchbox", name="Search")
            .fill("203.111.0.96/29")
        )
        await expect(admin_page.get_by_text("prefix from pool")).to_be_visible()
