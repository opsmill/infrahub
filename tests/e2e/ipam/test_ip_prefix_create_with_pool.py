"""Port of frontend/app/tests/e2e/ipam/ip-prefix-create-with-pool.spec.ts.

Allocate an IP prefix from the seeded "External prefixes pool". Depends on
data_scenario_branches (the full dataset): the asserted next-free prefix
(203.111.0.248/29) assumes the 30 site /29s plus the dropped-scenario ballast
/29 that slice replays — with sites alone the next-free would be .240/29.
"""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING

import pytest
from helpers import generate_random_branch_name
from playwright.sync_api import expect

if TYPE_CHECKING:
    from collections.abc import Generator

    from data.handles import ScenarioBranchesHandle
    from helpers import BranchAPI
    from playwright.sync_api import Page


class TestAllocateIpPrefixWithPool:
    @pytest.fixture
    def branch(
        self, branch_api: BranchAPI, data_scenario_branches: ScenarioBranchesHandle
    ) -> Generator[str, None, None]:
        name = generate_random_branch_name("ip-prefix-pool-")
        branch_api.create(name)
        yield name
        with contextlib.suppress(Exception):
            branch_api.delete(name)

    def test_create_an_ip_prefix_using_a_pool(self, admin_page: Page, branch: str) -> None:
        admin_page.goto(f"/ipam?branch={branch}")
        admin_page.get_by_test_id("create-object-button").click()

        admin_page.get_by_test_id("select-open-pool-option-button").click()
        admin_page.get_by_role("option", name="External prefixes pool").click()
        expect(admin_page.get_by_label("Prefix *")).to_contain_text("Allocated by pool")
        expect(admin_page.get_by_test_id("source-pool-badge")).to_contain_text("External prefixes pool")
        admin_page.get_by_role("textbox", name="Description").fill("prefix from pool")
        admin_page.get_by_role("button", name="Save").click()

        expect(admin_page.get_by_text("IP Prefix 203.111.0.248/29 created")).to_be_visible()
        admin_page.get_by_test_id("object-list-search-bar").get_by_role("searchbox", name="Search").fill(
            "203.111.0.248/29"
        )
        expect(admin_page.get_by_text("prefix from pool")).to_be_visible()
